# Touchless

Hands-free TikTok control for ECE 209AS.

A Freenove ESP32-S3 camera watches your hand. The board runs a landmark gesture model, decides when a pose counts, and types one Bluetooth keyboard key. TikTok scrolls, likes, or pauses when that window is focused.

## Start here

If you are taking over the hardware, follow:

**[PARTNER_BOOTUP.md](PARTNER_BOOTUP.md)**

That file has the plug-in steps, the two commands to start, Bluetooth pairing, and TikTok testing.

## Gestures

| Pose | Key | TikTok |
| --- | --- | --- |
| Index finger up | Up arrow | Next video |
| Index finger down | Down arrow | Previous video |
| Thumbs up | L | Like |
| Open palm | Space | Play / pause |
| No hand / unclear | none | No command |

A pose fires once. Drop your hand before the same pose can fire again.

## How the loop is split

| Step | Runs on |
| --- | --- |
| Camera frame | ESP32 |
| Hand skeleton | Laptop (class MediaPipe helper) |
| Gesture ML classification | ESP32 |
| Decision + cooldown | ESP32 |
| Bluetooth key | ESP32 |

The dashboard at http://127.0.0.1:8733 is a monitor and training UI. It is not the gesture classifier.

## Repo map

| Path | Purpose |
| --- | --- |
| `PARTNER_BOOTUP.md` | Partner day-1 boot guide |
| `firmware/` | ESP32 firmware |
| `dashboard/` | Live UI |
| `tools/serial_bridge.py` | USB bridge |
| `tools/hand_gestures.py` | Hand skeleton finder |
| `model/training/train_landmarks.py` | Landmark model trainer |
| `evaluation/user_study/` | 5-person study plan |
| `docs/hardware.md` | Pins and Freenove notes |
| `docs/course-requirements.md` | Course requirement mapping |

## Status

| Piece | Status |
| --- | --- |
| Camera + live preview | Working over USB serial |
| Landmark gesture model on ESP32 | Flashed and used for live poses |
| Bluetooth keyboard output | Implemented as **Touchless Keys** |
| TikTok demo | Needs a connected Bluetooth session and a focused TikTok window |
| User study | Protocol ready, no sessions run yet |
| Power numbers | Need a USB meter |

Older checklist notes: [WHAT_TO_DO.md](WHAT_TO_DO.md). Prefer `PARTNER_BOOTUP.md` for getting the board running.
