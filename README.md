# Touchless

Hands-free TikTok control for ECE 209AS. A Freenove ESP32-S3-WROOM watches a hand with its OV2640 camera, classifies the pose on the board, and types one keyboard key over Bluetooth.

The laptop dashboard only displays what the board already decided. It does not run the model.

## What is already in this repo

| Piece | Where | Status |
| --- | --- | --- |
| Dashboard | `dashboard/` | Interface built. Demo numbers are labeled sample data. |
| Firmware | `firmware/` | Both PlatformIO environments compile. Not flashed, and not tried on the board. |
| Trainer | `model/training/` | Runs in NumPy. A shape-sorting check reached 100% on toy drawings. That is not hand-gesture accuracy. |
| Weights on the board | `firmware/src/gesture_recognition/model_weights.cpp` | Placeholder. Gesture keys stay off until you train on real photos and reflash. |
| User study | `evaluation/user_study/` | Protocol and sheet. No participants have been run. |

## What you need to do

The remaining steps, with the commands, are in [WHAT_TO_DO.md](WHAT_TO_DO.md).

## Gestures

| Pose | Key | TikTok |
| --- | --- | --- |
| Index finger up | Up arrow | Next video |
| Index finger down | Down arrow | Previous video |
| Thumbs up | L | Like |
| Open palm | Space | Play / pause |
| Anything else | none | No command |

A pose fires once. It will not repeat until the camera returns to no gesture, and a cooldown blocks a second key even if the pose changes. Defaults are a confidence of 0.70, a neutral floor of 0.40, and a cooldown of 700 ms. The dashboard can change those on the board while the bridge is connected.

## Layout

| Path | Owner |
| --- | --- |
| `firmware/src/camera/` | Camera init and frames |
| `firmware/src/preprocessing/` | Scale to 64×64 grayscale |
| `firmware/src/gesture_recognition/` | On-device CNN |
| `firmware/src/decision/` | Threshold, latch, cooldown |
| `firmware/src/ble_hid/` | BLE keyboard |
| `dashboard/` | Monitor UI |
| `model/` | Dataset and training |
| `evaluation/` | Accuracy, latency, power, user study |
| `tools/` | Serial bridge and frame collector |

Pin map and the Freenove sources it comes from: `docs/hardware.md`. How this meets the course brief: `docs/course-requirements.md`.
