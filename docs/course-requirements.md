# Course requirements

Mapped to the ECE 209AS final brief. Items that still need a person and the board are marked as not done.

| Requirement | How this project meets it |
| --- | --- |
| Closed loop on an ESP32: sense, preprocess, infer, decide, act, feedback | Camera frame, 64×64 scale, on-device CNN, latch, BLE key. The LED blinks when a key is sent. The dashboard shows the decision after the fact. |
| At least one real sensing modality | Vision, which the brief lists (gesture recognition). |
| A learned model, on the ESP32, not on a laptop or in the cloud | The CNN in `gesture_classifier.cpp`. Training happens on a computer. Live frames are not sent out to be classified. |
| A real actuation | HID keys that move, like, and pause TikTok. A classification that does not pass the threshold does nothing. |
| Technical evaluation | Held-out accuracy and the float-vs-int8 comparison come from `model/training/train.py` after a real dataset exists. Latency is summarized from the serial log. RAM and flash come from the PlatformIO build and from `ESP.getFreeHeap()` / sketch size. Power needs a USB meter. None of these numbers have been measured on the board yet. |
| Usability evaluation, at least 5 participants | `evaluation/user_study/`. The sheet is ready. No sessions have been run, and this repo does not invent their results. |
| A baseline | Keyboard versus gesture on the same tasks, and float32 versus int8 weights on the same test images. |
| Deployment optimization | 64×64 gray input, one PSRAM frame buffer, stride-2 convolutions, int8 weight storage, confidence deadband, and a one-shot latch. |
| Idea, midterm, demo, final | `docs/milestones.md` lists what to show. Team ID is still blank. |

The live system is not demonstrated until the board is flashed, the model is trained on the team's hands, and a person can change a TikTok video with the four poses.
