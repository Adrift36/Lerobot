# Telegrip VR Controller Integration - Enhancement Plan

This document outlines the planned enhancements to integrate VR controller buttons with LeRobot's recording system.

## Overview

Currently, the telegrip teleoperator successfully records training data using VR controller input. The following enhancements are planned to improve the user experience and provide better control over the recording process:

## Planned Features

### 1. Episode Control via VR Buttons
- **A Button**: Accept/save current episode and start reset phase
- **B Button**: Discard current episode and restart it
- These allow users to control recording without needing keyboard input

### 2. Motor Torque Control via Thumbstick
- **Thumbstick Press**: Toggle motor torque on/off
  - When OFF: Motors can be moved by hand for manual repositioning
  - When ON: Re-engage motors at current position
  - Position tracking continues regardless of torque state
  - Useful for helping robot recover from kinematic singularities

### 3. Free Movement Between Episodes
- Allow users to move the arm between episodes
- Configure reset time duration
- No recording during reset phase

## Implementation Roadmap

### Phase 1: VR Button Event System (High Priority)

**Changes needed:**

1. **Telegrip VR WebSocket Server** (`telegrip/telegrip/inputs/vr_ws_server.py`)
   - Capture A/B button and thumbstick press events
   - Add event queue for button presses
   - Expose `get_vr_events()` method

2. **Telegrip Teleoperator** (`src/lerobot/teleoperators/telegrip/telegrip_teleop.py`)
   - Add `get_vr_events()` method to expose button presses
   - Add `set_motor_torque(enabled: bool)` method
   - Maintain state of motor engagement

3. **Recording Script** (`src/lerobot/scripts/lerobot_record.py`)
   - Check for VR button events during recording loop
   - Set `events["exit_early"]` when A button pressed (end episode)
   - Set `events["rerecord_episode"]` when B button pressed (restart episode)

### Phase 2: Motor Torque Control (Medium Priority)

**Changes needed:**

1. **SO100 Follower Robot** (`src/lerobot/robots/so100_follower/so100_follower.py`)
   - Add `disengage_motors()` method (disable all torque)
   - Add `engage_motors()` method (enable all torque)
   - Ensure position tracking continues during disengaged state

2. **Telegrip Teleoperator**
   - Pass thumbstick events to robot interface
   - Implement torque toggle logic

3. **Recording Loop**
   - Handle thumbstick press events
   - Call robot torque control methods

## Technical Notes

### VR Button Data Structure
The telegrip system needs to track:
- `buttonA_pressed` (bool): A button state
- `buttonB_pressed` (bool): B button state
- `thumbstick_pressed` (bool): Thumbstick click state
- Button press events should be one-time triggers, not continuous states

### Event Queue
Use a thread-safe queue for VR button events:
```python
from queue import Queue
self.vr_events_queue = Queue()

# When button pressed in VR server:
self.vr_events_queue.put({'type': 'button_a', 'timestamp': time.time()})

# In teleoperator:
def get_vr_events(self):
    events = []
    while not self.vr_events_queue.empty():
        events.append(self.vr_events_queue.get_nowait())
    return events
```

### Motor Torque States
- During recording: Motors torque-enabled (following VR commands)
- Thumbstick press: Toggle torque
  - Dis engaged: Position tracked, no torque
  - Re-engaged: Position tracked, torque applied
- Position values should be continuous regardless of torque state

## Integration Points

1. **Telegrip System** → **VR WebSocket Server**
   - Capture button/thumbstick events
   - Pass events to control loop

2. **Control Loop** → **Teleoperator**
   - Expose events via `get_vr_events()`

3. **Teleoperator** → **Recording Script**
   - Provide VR events
   - Receive torque control commands

4. **Recording Script** → **Robot Interface**
   - Call `engage_motors()` / `disengage_motors()`
   - Update `events` dict based on VR button presses

## Testing Checklist

- [ ] A button terminates episode correctly
- [ ] B button restarts episode correctly
- [ ] Thumbstick press toggles torque
- [ ] Position tracked during disengaged torque
- [ ] Position data recorded correctly throughout
- [ ] Multiple episodes can be recorded in sequence
- [ ] Robot can be manually moved when disengaged

## Future Enhancements

- Haptic feedback on VR controllers (vibration on button press)
- Visual feedback on controllers (indicator of motor state)
- Gesture recognition for multi-button combinations
- Episode progress display on VR interface
