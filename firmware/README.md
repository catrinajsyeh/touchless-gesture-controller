# Firmware

PlatformIO project for the Freenove ESP32-S3-WROOM. The default environment talks to the CH343 USB-serial port (UART0 on GPIO43/GPIO44) at 460800 baud. PSRAM is octal, which the camera frame buffer needs. Flash size is 8 MB so the same image boots on both the N8R8 and N16R8 modules. A 16 MB module simply leaves the extra flash unused.

## Build and flash

Install PlatformIO, then from this directory:

```bash
pio run -e freenove_esp32s3_uart
pio run -e freenove_esp32s3_uart -t upload --upload-port COM5
pio device monitor -e freenove_esp32s3_uart --port COM5
```

Replace `COM5` with the port Windows actually assigns.

If upload works but the monitor stays silent, you are likely on the native USB-C port (GPIO19/GPIO20). Build the other environment instead:

```bash
pio run -e freenove_esp32s3_usb -t upload --upload-port COM5
pio device monitor -e freenove_esp32s3_usb --port COM5
```

The first lines should be JSON, including `{"type":"boot"...}` and either a camera-ready log or a ribbon-cable error.

## What each folder does

- `src/main.cpp` runs the loop: read a command, grab one frame, scale it, classify, decide, maybe tap a key, print JSON.
- `src/camera/` starts the OV2640 on the Freenove ESP32-S3-EYE pin map and returns the frame buffer.
- `src/preprocessing/` nearest-neighbor scales that frame to 64×64 and normalizes it to about -1..1.
- `src/gesture_recognition/` is the small CNN. Until `model_weights.cpp` says the model is trained, every frame is reported as not trained and no gesture key is sent.
- `src/decision/` is the latch and cooldown. The same rules are checked by `evaluation/test_decision_model.py`.
- `src/ble_hid/` advertises as `Touchless Keys` and sends an 8-byte keyboard report, then a release report.
- `src/telemetry/` is the JSON line protocol shared with `tools/serial_bridge.py`.

Manual commands, one JSON object per line:

```json
{"cmd":"keytest","key":"up"}
{"cmd":"suspend","value":1}
{"cmd":"set","name":"threshold","value":0.75}
```

`keytest` is the only path that sends a key before the model is trained. `up`, `down`, `l`, and `space` are the four TikTok keys.

## Compile result

Both environments compiled on this computer. They have not been flashed, and the camera and Bluetooth have not been tried on the board. The UART build uses 81,396 bytes of internal RAM (24.8%) and 997,861 bytes of flash (23.8% of the 4 MB app partition). The native-USB build is slightly smaller. Those figures are the compiled program, not free memory while the camera is running. The link uses the octal-PSRAM SDK (`qio_opi`) even though PlatformIO's board title still says "No PSRAM".
