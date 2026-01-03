# Telegrip LeRobot Integration - Checkpoint Summary

**Date**: January 3, 2026  
**Status**: Working and Recording Data ✅

## What We've Built

A complete telegrip teleoperator integration that allows recording robot training data using VR controller input instead of a physical leader arm.

### Architecture Overview

```
Quest VR Headset
    ↓
Telegrip VR WebSocket Server (wss://192.168.0.183:8442)
    ↓
Telegrip IK Solver (computes joint angles from VR position/rotation)
    ↓
TelegripTeleoperator (LeRobot integration layer)
    ↓
LeRobot Recording Script
    ├→ Gets actions (joint positions) from telegrip
    ├→ Sends actions to physical SO100 follower arm
    ├→ Captures observations (joint states, camera frames)
    └→ Saves dataset in LeRobot format
```

## Files Created

### 1. Telegrip Teleoperator Module
- **`src/lerobot/teleoperators/telegrip/__init__.py`**
  - Module exports for config and teleoperator classes

- **`src/lerobot/teleoperators/telegrip/config_telegrip.py`**
  - Configuration dataclass with telegrip-specific parameters
  - Single-arm mode (right arm only)
  - VR, keyboard, PyBullet, and robot connectivity options
  - Registered as `"telegrip"` teleoperator type

- **`src/lerobot/teleoperators/telegrip/telegrip_teleop.py`**
  - Main `TelegripTeleoperator` class implementing LeRobot interface
  - Runs telegrip in background thread (doesn't block recording loop)
  - Provides joint angle actions via `get_action()`
  - Features:
    - Thread-safe telegrip integration
    - Proper connection/disconnection lifecycle
    - Error handling and logging

### 2. Integration Points
- **`src/lerobot/scripts/lerobot_record.py`**
  - Added `telegrip` import to register the teleoperator

- **`telegrip/config.yaml`**
  - Fixed URDF path (was `URDF/SO100/urdf/so100.urdf`, now `URDF/SO100/so100.urdf`)

## Usage

### Basic Recording Command

```bash
lerobot-record \
    --robot.type=so100_follower \
    --robot.port=/dev/ttyACM0 \
    --robot.id=robot_arm \
    --robot.cameras="{ front: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30}}" \
    --teleop.type=telegrip \
    --teleop.bimanual=false \
    --teleop.enable_robot=false \
    --teleop.enable_vr=true \
    --teleop.enable_keyboard=true \
    --teleop.id=my_telegrip \
    --display_data=true \
    --dataset.repo_id=local/my_dataset \
    --dataset.root=./data \
    --dataset.push_to_hub=false \
    --dataset.num_episodes=10 \
    --dataset.episode_time_s=60
```

### Key Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--teleop.type` | - | Must be `telegrip` |
| `--teleop.bimanual` | False | Single-arm mode (right arm) |
| `--teleop.enable_robot` | False | Don't connect physical leader, use IK only |
| `--teleop.enable_vr` | True | Enable VR controller input |
| `--teleop.enable_keyboard` | True | Enable keyboard fallback |
| `--teleop.enable_pybullet` | True | Use PyBullet for IK visualization |
| `--teleop.enable_pybullet_gui` | True | Show PyBullet GUI |

## Data Flow During Recording

1. **VR Controller Input** (Quest 1 Headset)
   - Position: 3D hand position in VR space
   - Rotation: Hand orientation (quaternion)
   - Trigger: Gripper control

2. **Telegrip Processing**
   - IK solver computes joint angles from VR hand pose
   - Runs in background thread (async event loop)
   - Computes for both left and right arms (uses right arm only)

3. **LeRobot Recording Loop**
   - Calls `telegrip.get_action()` at 30 Hz (configurable)
   - Gets 6 joint angles + gripper: `[shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper]`
   - Sends to physical SO100 follower arm via serial port
   - Captures robot observations (joint positions, forces, torques)
   - Records camera frames from USB cameras
   - Saves frames as `.parquet` files and video

4. **Dataset Output**
   - Format: `./data/local/{dataset_name}/`
   - Structure: LeRobot standard format
   - Can be used directly for policy training

## Current Capabilities

✅ **Working**
- VR controller input captured and processed
- Joint angles computed via telegrip IK solver
- Actions sent to physical robot arm at 30 Hz
- Robot observations recorded (positions, velocities, etc.)
- Camera frames captured and saved
- Multiple episodes can be recorded sequentially
- Dataset saved in LeRobot format

✅ **Tested**
- Single episode with VR controller movement recorded successfully
- Data verified to contain:
  - Actions from VR controller (changing joint angles)
  - Observations from robot (mirroring actions)
  - Camera frames from USB cameras
  - Metadata and task descriptions

## Known Limitations & TODO

### Immediate Improvements Needed
- [ ] VR button integration for episode control (A/B buttons)
- [ ] Thumbstick for motor torque toggle
- [ ] Proper error handling for VR disconnection
- [ ] Episode reset phase (move arm between episodes without recording)

### Future Enhancements
- [ ] Haptic feedback (vibration on button press)
- [ ] VR UI status display (recording/reset/waiting)
- [ ] Support for bimanual recording (left + right arms)
- [ ] Demo mode playback in VR
- [ ] Gesture-based episode control

## Development Notes

### Thread Architecture
The telegrip system runs in a background daemon thread to prevent blocking the main LeRobot recording loop:

```python
def run_telegrip_in_thread():
    self._loop = asyncio.new_event_loop()
    asyncio.set_event_loop(self._loop)
    try:
        self._loop.run_until_complete(self._telegrip_system.start())
        self._loop.run_forever()  # Keep running for background tasks
    finally:
        self._loop.close()

self._telegrip_thread = threading.Thread(
    target=run_telegrip_in_thread, 
    daemon=True
)
self._telegrip_thread.start()
```

### Event Loop Lifecycle
- **Connect**: Starts telegrip in background thread
- **Get Action**: Reads current joint angles from telegrip (non-blocking)
- **Disconnect**: Signals telegrip loop to stop, waits for cleanup

### Joint Angle Units
- All joint angles in **degrees** (not radians)
- Ranges from telegrip URDF:
  - shoulder_pan: -114.6° to 114.6°
  - shoulder_lift: -100.3° to 100.3°
  - elbow_flex: -90.0° to 90.0°
  - wrist_flex: -113.2° to 98.8°
  - wrist_roll: -180.0° to 180.0°
  - gripper: -11.5° to 114.6°

## Next Steps

1. **Phase 1**: Add VR button event system (see `TELEGRIP_ENHANCEMENT_PLAN.md`)
2. **Phase 2**: Implement motor torque control
3. **Phase 3**: Add bimanual support
4. **Phase 4**: Polish UI and error handling

## Files to Review

Key files for future modifications:
- `src/lerobot/teleoperators/telegrip/telegrip_teleop.py` - Main integration
- `src/lerobot/scripts/lerobot_record.py` - Recording loop
- `telegrip/telegrip/inputs/vr_ws_server.py` - VR input handling
- `telegrip/telegrip/control_loop.py` - Telegrip main control
- `telegrip/telegrip/core/robot_interface.py` - Motor control interface

## References

- **LeRobot Recording**: `src/lerobot/scripts/lerobot_record.py`
- **Teleoperator Base Class**: `src/lerobot/teleoperators/teleoperator.py`
- **Telegrip System**: `telegrip/telegrip/main.py`
- **Recording Events**: `src/lerobot/utils/control_utils.py` (init_keyboard_listener)
