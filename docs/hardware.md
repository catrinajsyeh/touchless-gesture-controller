# Hardware

The board in this project is the Freenove ESP32-S3-WROOM kit (Freenove product family FNK0085). The ESP32-S3-WROOM-1 module does not contain the image sensor. The kit's camera is an OV2640 on a 24-pin DVP ribbon that plugs into the connector on the carrier. The sensor ID is read at boot because a few modules report a different OmniVision part on the same connector. The GPIO map does not change with the sensor.

Freenove documents that map as `CAMERA_MODEL_ESP32S3_EYE` and in the camera pin table for the ESP32-S3 WROOM:

- [camera_pins.h](https://github.com/Freenove/Freenove_ESP32_S3_WROOM_Board/blob/main/C/Sketches/Sketch_07.2_As_VideoWebServer/camera_pins.h) (`CAMERA_MODEL_ESP32S3_EYE`)
- [Freenove camera chapter](https://docs.freenove.com/projects/fnk0086/en/latest/fnk0086/codes/tutorial/3_Camera_Web_Server.html), which selects that macro
- [Pin preface](https://docs.freenove.com/projects/fnk0086/en/latest/fnk0086/codes/tutorial/Preface.html)
- [N8R8 and N16R8](https://docs.freenove.com/projects/fnk0099/en/latest/fnk0099/codes/C/Preface.html): black PCB is 8 MB flash + 8 MB PSRAM, red PCB is 16 MB flash + 8 MB PSRAM. Octal PSRAM uses GPIO35–GPIO37, so those pins are not used here.
- [UART versus native USB](https://docs.freenove.com/projects/fnk0099/en/latest/fnk0099/codes/C/1_LED.html)
- OV2640 datasheet in the same Freenove repository

| Camera signal | GPIO |
| --- | --- |
| SIOD (SCCB SDA) | 4 |
| SIOC (SCCB SCL) | 5 |
| VSYNC | 6 |
| HREF | 7 |
| Y4 / D2 | 8 |
| Y3 / D1 | 9 |
| Y5 / D3 | 10 |
| Y2 / D0 | 11 |
| Y6 / D4 | 12 |
| PCLK | 13 |
| XCLK | 15 |
| Y9 / D7 | 16 |
| Y8 / D6 | 17 |
| Y7 / D5 | 18 |
| PWDN | not wired |
| RESET | not wired |

The status LED is GPIO2, active high, from Freenove's LED chapter. GPIO43 and GPIO44 are the CH343 UART. GPIO19 and GPIO20 are native USB. Bluetooth does not need a pin.

Capture is QQVGA RGB565 (160×120) into one PSRAM frame buffer. The model input is a 64×64 grayscale thumbnail made on the board. XCLK is tried at 20 MHz and then 10 MHz, which is the clock Freenove uses in the camera web server example.
