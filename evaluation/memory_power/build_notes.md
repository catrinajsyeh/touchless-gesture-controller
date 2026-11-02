# Compile-time size

Measured by `pio run` on this computer. This is not a measurement from a running board, and it is not power.

| Environment | Internal RAM | Flash (of the 4 MB app partition) |
| --- | --- | --- |
| `freenove_esp32s3_uart` | 81,396 bytes (24.8%) | 997,861 bytes (23.8%) |
| `freenove_esp32s3_usb` | 81,180 bytes (24.8%) | 983,757 bytes (23.5%) |

The image is built for 8 MB flash with octal PSRAM (`qio_opi`). PlatformIO's board title still says "No PSRAM" because that is the name of the generic ESP32-S3 board entry. The linked SDK is the PSRAM one.

Free heap, free PSRAM, and sketch size while the camera and Bluetooth are running still have to be read from the board's status JSON after you flash it.
