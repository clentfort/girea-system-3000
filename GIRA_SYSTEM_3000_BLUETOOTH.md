# Gira System 3000 Bluetooth Protocol Documentation

This document describes the binary protocol used by Gira System 3000 Bluetooth devices (specifically shutter controllers) and compares it with the current Home Assistant integration.

## Binary Message Structure

The protocol uses a consistent binary structure for both commands (write) and status updates (broadcast/notification).

### Structure Overview

`[MessageType] [ObjectID (2 bytes)] [ElementsNum] [PropertyID] [StartIndex] [ValueLength] [Value...]`

| Field | Length | Description |
| :--- | :--- | :--- |
| **MessageType** | 1 byte | `0xF6` (246) for Write/Command, `0xF7` (247) for Notification/Broadcast. |
| **ObjectID** | 2 bytes | The ID of the device object. For the shutter controller, this is `800` (`0x0320`). |
| **ElementsNum**| 1 byte | Number of elements being addressed. Typically `0x01`. |
| **PropertyID** | 1 byte | The ID of the parameter or property (e.g., Move, Position). |
| **StartIndex** | 1 byte | Typically `0x10` (representing index 1). |
| **ValueLength** | 1 byte | Length of the value field in bytes. |
| **Value** | Variable| The actual data (binary, scaling, or enum). |

---

## Key Property IDs (PIDs)

Based on the analysis of the Gira JavaScript source, the following Property IDs are used for the Shutter Controller (Object 800):

| Property ID | Hex | Name | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| 255 | `0xFF` | `PID_Move UpDown` | PDT_BINARY | `0`: Up, `1`: Down |
| 254 | `0xFE` | `PID_StopStep UpDown` | PDT_BINARY | `0`: Step Up, `1`: Step Down |
| 253 | `0xFD` | `PID_STOP` | PDT_BINARY | `0`: Stop |
| 252 | `0xFC` | `PPID_Set_Absolute_Position_Blinds` | PDT_SCALING | 0-100% (mapped to 255-0) |
| 251 | `0xFB` | `PPID_Set_Absolute_Position_Slat` | PDT_SCALING | 0-100% (mapped to 255-0) |
| 247 | `0xF7` | `PID_INFO_MOVE_UP_DOWN_STOP` | PDT_ENUM8 | Status: 0-1 Stopped, >1 Moving |
| 246 | `0xF6` | `PID_CURRENT_ABSOLUTE_POSITION_BLINDS`| PDT_SCALING | Read-only blind position |
| 245 | `0xF5` | `PID_CURRENT_ABSOLUTE_POSITION_SLATS` | PDT_SCALING | Read-only slat position |
| 162 | `0xA2` | `PID_OPERATION_MODE` | PDT_ENUM8 | `0`: Blinds (with slats), `1`: Roller Shutter |

---

## Command Construction Examples

### Move Down
- **Message Type**: `0xF6` (Write)
- **Object ID**: `0x0320` (800)
- **Elements**: `0x01`
- **PID**: `0xFF` (Move)
- **Start Index**: `0x10` (1)
- **Length**: `0x01`
- **Value**: `0x01` (Down)
- **Full Hex**: `F6 03 20 01 FF 10 01 01`

### Set Blind Position to 50%
- **Value Calculation**: `(100 - 50) * 255 / 100 = 127.5` -> `127` (`0x7F`)
- **PID**: `0xFC`
- **Full Hex**: `F6 03 20 01 FC 10 01 7F`

---

## Broadcast Parsing

The device periodically broadcasts its state via Manufacturer Data (Manufacturer ID `1412`).

### Blind Position Update
The prefix for a blind position broadcast is `F7 03 20 01 F6 10 01`.
The byte immediately following this prefix is the raw position value (`0-255`).

**Conversion to Home Assistant (0-100%):**
`HA_Position = round(100 * (255 - RawValue) / 255)`

---

## Comparison with Current Implementation

The current implementation in `gira_ble.py` and `cover.py` handles the core functionality but lacks support for advanced features.

### Currently Supported
- **Movement**: Up, Down, Stop, and Step (Tilt) Up/Down are supported.
- **Absolute Position**: Setting and reading the blind position (0-100%) is supported.
- **Passive Updates**: The integration correctly parses blind position broadcasts.

### Missing / Not Handled
- **Slat Control (Tilt)**:
    - Setting absolute slat position (`PID 0xFB`) is not implemented.
    - Reading slat position from broadcasts (`PID 0xF5`) is not implemented.
- **Moving Status**:
    - The integration does not use `PID 0xF7` to detect if the shutter is currently in motion.
- **Operation Mode Detection**:
    - The integration assumes a standard shutter. It does not read `PID 0xA2` to determine if the device is in "Blinds" mode (supporting slats) or "Roller Shutter" mode.
- **Configuration Properties**:
    - Advanced settings like ventilation positions, move times, and inverse mode are currently ignored.

---

## Device Templates & UI

The Gira app determines the UI layout (one slider vs. two sliders) based on two factors:
1. `PID_OPERATION_MODE` (`0` = Blinds, `1` = Roller Shutter)
2. `LOCAL_OPERATION_ELEMENT_SELECTION` (Custom property for UI selection)

If `OperationMode == 0` (Blinds), the device supports both blind position and slat position.
