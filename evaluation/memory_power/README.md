# Memory and power

## Memory and flash

The compiled size is in `build_notes.md`. That is the program size, not free RAM while the camera is running. The dashboard's live memory figures come from `ESP.getFreeHeap()` and `ESP.getSketchSize()` in the status JSON. Those fields stay empty until the board is connected. Do not copy the sample numbers from demo mode into a report.

## Power

The ESP32-S3 on this Freenove board does not expose a current sensor to the sketch. Measure power outside the chip:

1. Put a USB power meter between the laptop and the board, on the port that is powering it.
2. Record current and voltage while the board is idle (camera on, no hand), while it is classifying, and while Bluetooth is connected.
3. Write the three readings in the table below. Leave the cells blank until you have them.

| Condition | Voltage | Current | Power |
| --- | --- | --- | --- |
| Advertising, camera on | | | |
| Classifying | | | |
| BLE connected, key sent | | | |

Multiply voltage by current if the meter does not show watts. Say which USB port you measured. The native USB port and the UART port are not the same cable.
