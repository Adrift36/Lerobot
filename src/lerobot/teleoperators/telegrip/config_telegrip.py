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

from dataclasses import dataclass

from ..config import TeleoperatorConfig


@TeleoperatorConfig.register_subclass("telegrip")
@dataclass
class TelegripConfig(TeleoperatorConfig):
    """Configuration for telegrip VR/keyboard teleoperator for SO100 robots.
    
    Telegrip is a VR and keyboard-based teleoperation system for controlling
    SO100 robot arms. It supports both single and bimanual control.
    
    Attributes:
        bimanual: Whether to control both arms (default: False)
        left_arm_port: Serial port for left arm (e.g., "/dev/ttyUSB0")
        right_arm_port: Serial port for right arm (e.g., "/dev/ttyUSB1")
        https_port: HTTPS server port for web interface (default: 8443)
        websocket_port: WebSocket port for VR controllers (default: 8442)
        host_ip: Host IP address (default: "0.0.0.0")
        log_level: Logging level (default: "warning")
        autoconnect: Automatically connect to robot on startup (default: False)
        enable_robot: Whether to enable robot hardware connection (default: True)
        enable_pybullet: Whether to enable PyBullet simulation (default: True)
        enable_pybullet_gui: Whether to enable PyBullet GUI visualization (default: True)
        enable_vr: Whether to enable VR WebSocket server (default: True)
        enable_keyboard: Whether to enable keyboard input (default: True)
    """
    
    # Arm configuration
    bimanual: bool = False
    left_arm_port: str | None = None
    right_arm_port: str = "/dev/ttyACM0"
    
    # Network configuration
    https_port: int = 8443
    websocket_port: int = 8442
    host_ip: str = "0.0.0.0"
    
    # System configuration
    log_level: str = "warning"
    autoconnect: bool = False
    enable_robot: bool = True
    enable_pybullet: bool = True
    enable_pybullet_gui: bool = True
    enable_vr: bool = True
    enable_keyboard: bool = True