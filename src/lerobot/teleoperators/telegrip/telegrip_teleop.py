#!/usr/bin/env python

# Copyright 2024 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import logging
import threading
import time
from typing import Optional

import numpy as np

from lerobot.teleoperators.utils import TeleopEvents
from lerobot.utils.errors import DeviceAlreadyConnectedError, DeviceNotConnectedError

from ..teleoperator import Teleoperator
from .config_telegrip import TelegripConfig

logger = logging.getLogger(__name__)


class TelegripTeleoperator(Teleoperator):
    """
    Telegrip VR and Keyboard Teleoperator for SO100 Robot Arms.
    
    This teleoperator integrates the telegrip system (VR controllers + keyboard input)
    with LeRobot's recording pipeline. It allows recording training data using VR or
    keyboard as the leader input.
    
    The telegrip system runs in a separate thread and provides arm joint positions
    that are converted to the action format expected by LeRobot.
    """

    config_class = TelegripConfig
    name = "telegrip"

    def __init__(self, config: TelegripConfig):
        super().__init__(config)
        self.config = config
        self._telegrip_system = None
        self._is_connected = False
        self._telegrip_thread = None
        self._last_action = None
        self._loop = None
        
        # Cache for arm state
        self._left_arm_angles = np.zeros(6)
        self._right_arm_angles = np.zeros(6)

        
        # Motor names matching SO100 arms
        self._motor_names = [
            "shoulder_pan",
            "shoulder_lift", 
            "elbow_flex",
            "wrist_flex",
            "wrist_roll",
            "gripper"
        ]

    @property
    def action_features(self) -> dict[str, type]:
        """Define the action features for telegrip.
        
        For bimanual control, actions are prefixed with 'left_' and 'right_'.
        For single arm, actions use no prefix.
        """
        if self.config.bimanual:
            return {f"left_{motor}.pos": float for motor in self._motor_names} | {
                f"right_{motor}.pos": float for motor in self._motor_names
            }
        else:
            return {f"{motor}.pos": float for motor in self._motor_names}

    @property
    def feedback_features(self) -> dict[str, type]:
        """Telegrip doesn't support feedback (no haptics)."""
        return {}

    @property
    def is_connected(self) -> bool:
        """Check if telegrip system is running and robot is engaged."""
        if self._telegrip_system is None:
            return False
        return self._telegrip_system.is_running and self._is_connected

    def connect(self, calibrate: bool = True) -> None:
        """Start the telegrip system and connect to robots.
        
        Args:
            calibrate: If True, calibration will be performed if needed.
                      (Not applicable for telegrip, included for API compatibility)
        """
        if self.is_connected:
            raise DeviceAlreadyConnectedError(f"{self} already connected")

        logger.info("Starting telegrip system...")
        
        try:
            # Import telegrip here to avoid circular dependencies
            from telegrip import TelegripConfig as TelegripSystemConfig
            from telegrip.main import TelegripSystem
            
            # Create telegrip configuration from our config
            telegrip_config = TelegripSystemConfig(
                follower_ports={
                    "left": self.config.left_arm_port or "/dev/ttySO100red",  # Fallback port
                    "right": self.config.right_arm_port
                },
                enable_robot=self.config.enable_robot,
                enable_pybullet=self.config.enable_pybullet,
                enable_pybullet_gui=self.config.enable_pybullet_gui,
                enable_vr=self.config.enable_vr,
                enable_keyboard=self.config.enable_keyboard,
                autoconnect=self.config.autoconnect,
                log_level=self.config.log_level,
                https_port=self.config.https_port,
                websocket_port=self.config.websocket_port,
                host_ip=self.config.host_ip,
            )
            
            # Create and start telegrip system
            self._telegrip_system = TelegripSystem(telegrip_config)
            
            # Run telegrip in a separate thread with its own event loop
            def run_telegrip_in_thread():
                """Run telegrip system in a separate thread."""
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
                try:
                    self._loop.run_until_complete(self._telegrip_system.start())
                    # Keep the loop running for background tasks
                    self._loop.run_forever()
                except Exception as e:
                    logger.error(f"Error in telegrip thread: {e}")
                finally:
                    self._loop.close()
            
            # Start telegrip in background thread
            self._telegrip_thread = threading.Thread(target=run_telegrip_in_thread, daemon=True)
            self._telegrip_thread.start()
            
            # Wait a bit for telegrip to fully start up
            time.sleep(2)
            
            # Auto-engage robot if configured
            if self.config.autoconnect and self.config.enable_robot:
                logger.info("Auto-engaging robot motors...")
                time.sleep(1)  # Give more time for connection
                if self._telegrip_system.control_loop and self._telegrip_system.control_loop.robot_interface:
                    self._telegrip_system.control_loop.robot_interface.engage()
            
            self._is_connected = True
            logger.info(f"{self} connected successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect telegrip: {e}")
            self._is_connected = False
            raise

    @property
    def is_calibrated(self) -> bool:
        """Telegrip doesn't require calibration."""
        return True

    def calibrate(self) -> None:
        """Telegrip doesn't require calibration (no-op)."""
        pass

    def configure(self) -> None:
        """Apply any configuration to telegrip.
        
        For now, this is a no-op as telegrip handles its own configuration.
        """
        pass

    def get_action(self) -> dict[str, float]:
        """Get current arm joint positions from telegrip.
        
        Returns:
            Dictionary of motor positions in the format expected by LeRobot.
            For bimanual: {"left_motor.pos": val, "right_motor.pos": val, ...}
            For single: {"motor.pos": val, ...}
        """
        if not self.is_connected:
            raise DeviceNotConnectedError(
                "Telegrip is not connected. You need to run `connect()` before `get_action()`."
            )

        try:
            action = {}
            
            if self._telegrip_system.control_loop.robot_interface:
                robot_interface = self._telegrip_system.control_loop.robot_interface
                
                if self.config.bimanual:
                    # Get left arm angles
                    left_angles = robot_interface.get_arm_angles("left")
                    for motor_name, angle in zip(self._motor_names, left_angles):
                        action[f"left_{motor_name}.pos"] = float(angle)
                    
                    # Get right arm angles
                    right_angles = robot_interface.get_arm_angles("right")
                    for motor_name, angle in zip(self._motor_names, right_angles):
                        action[f"right_{motor_name}.pos"] = float(angle)
                else:
                    # Single arm (use right arm)
                    right_angles = robot_interface.get_arm_angles("right")
                    for motor_name, angle in zip(self._motor_names, right_angles):
                        action[f"{motor_name}.pos"] = float(angle)
            else:
                logger.warning("Robot interface not available in telegrip system")
            
            self._last_action = action
            return action
            
        except Exception as e:
            logger.error(f"Error getting action from telegrip: {e}")
            raise

    def _drain_vr_events(self) -> list[dict]:
        """Drain VR events from the telegrip system if available."""
        if not self._telegrip_system or not hasattr(self._telegrip_system, "get_vr_events"):
            return []

        try:
            return self._telegrip_system.get_vr_events()
        except Exception as e:
            logger.warning(f"Error pulling VR events from telegrip: {e}")
            return []

    def get_teleop_events(self) -> dict[str, bool]:
        """Expose VR controller button events as teleop control signals."""
        events = {
            TeleopEvents.SUCCESS.value: False,
            TeleopEvents.FAILURE.value: False,
            TeleopEvents.RERECORD_EPISODE.value: False,
            TeleopEvents.IS_INTERVENTION.value: False,
            TeleopEvents.TERMINATE_EPISODE.value: False,
        }

        for event in self._drain_vr_events():
            event_type = event.get("type")

            if event_type == "button_a":
                logger.info("Telegrip: button A event received -> terminate episode (mark success)")
                events[TeleopEvents.SUCCESS.value] = True
                events[TeleopEvents.TERMINATE_EPISODE.value] = True
            elif event_type == "button_b":
                logger.info("Telegrip: button B event received -> terminate and rerecord episode")
                events[TeleopEvents.RERECORD_EPISODE.value] = True
                events[TeleopEvents.TERMINATE_EPISODE.value] = True

        return events

    def send_feedback(self, feedback: dict[str, float]) -> None:
        """Send feedback to telegrip (not implemented - telegrip doesn't support haptics)."""
        # Could implement vibration feedback in the future
        pass

    def disconnect(self) -> None:
        """Stop the telegrip system and disconnect from robots."""
        if not self.is_connected:
            raise DeviceNotConnectedError(f"{self} is not connected.")

        logger.info("Stopping telegrip system...")
        
        try:
            if self._telegrip_system and self._loop:
                # Schedule stop in the telegrip event loop and wait briefly
                fut = asyncio.run_coroutine_threadsafe(self._telegrip_system.stop(), self._loop)
                try:
                    fut.result(timeout=5)
                except Exception as e:
                    logger.warning(f"Timed out or failed stopping telegrip cleanly: {e}")

                # Stop the event loop
                self._loop.call_soon_threadsafe(self._loop.stop)
                
                # Wait for thread to finish (with timeout)
                if self._telegrip_thread:
                    self._telegrip_thread.join(timeout=5)
                
                self._loop = None
                self._telegrip_system = None
                self._telegrip_thread = None
            
            self._is_connected = False
            logger.info(f"{self} disconnected successfully")
            
        except Exception as e:
            logger.error(f"Error disconnecting telegrip: {e}")
            raise