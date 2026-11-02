# Architecture

Someone watching TikTok on a laptop should be able to change the video without touching the keyboard. The intelligence that has to be local is the pose decision: the frame is a picture of the person's hand, and sending that stream to the laptop would add a radio hop and would move inference off the device. The ESP32-S3 sees a 64×64 grayscale crop, runs a small convolutional network, and emits one HID key. The laptop's only job in the control path is to deliver that key to the focused TikTok window.

```
OV2640  →  QQVGA RGB565 in PSRAM  →  64×64 gray
        →  int8 weights, float conv on the S3
        →  threshold, neutral latch, cooldown
        →  BLE HID key up / key down
        →  TikTok in the focused window
```

A USB serial JSON stream copies the thumbnail and the decision to the dashboard. That copy is a monitor. The bridge never classifies pixels.

## Why this model

The network is three stride-2 3×3 convolutions (16, 32, then 48 filters), a four-quadrant average pool, and a 5-way classifier. Quadrant pooling keeps "finger in the top half" distinct from "finger in the bottom half," which a single global average would blur. Weights are stored as int8 with a per-tensor scale and expanded to float in PSRAM at boot. The S3 has a floating-point unit, and the network is small enough that a generic vision backbone is unnecessary. Training compares the float weights with the dequantized int8 weights on the same held-out images. That comparison is the deployment-optimization baseline. The other baseline is the keyboard, measured in the user study.

## What can go wrong

These are expected risks, not measured results:

- Point-up and thumbs-up can look alike if the thumb is not clearly off to the side.
- A bright window behind the hand can dominate a 64×64 frame.
- Windows drops a BLE HID link if the board resets. The firmware starts advertising again. The user may still need to click the device in Bluetooth settings.
- TikTok ignores keys when the video page is not focused.
- The placeholder weights are not a gesture model. Until training replaces them, the board will refuse to send gesture keys.
