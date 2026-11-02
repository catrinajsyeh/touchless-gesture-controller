# Milestones

Put the team ID on every slide. The ID is not in this repo yet.

## Idea presentation

3 minutes, up to 5 slides.

- User: a person watching TikTok on a laptop who cannot, or does not want to, touch the keyboard.
- Sensing: the Freenove OV2640.
- Model: 5-way pose classification, trained on our own frames.
- Actuation: BLE HID keys Up, Down, L, and Space.
- Why the ESP32-S3: it has the camera, PSRAM for a frame, and BLE, so the decision never leaves the board.
- Baseline: the same tasks done with the keyboard. Success: correct key, one shot per pose, tolerable delay.
- Storyboard: idle, index up, thumbs up, open palm, return to empty hand.

## Midterm

5 minutes.

- Video of the camera path. The serial log's first-frame checksum is the early proof, then the dashboard thumbnail.
- Model running on the ESP32. This requires a trained `model_weights.cpp` and a reflash. The placeholder does not count.
- One real key, shown with the manual key test and then with a pose.
- Accuracy on the held-out set from `model/deployment/metrics.json`.
- One bottleneck. Likely candidates: BLE reconnects, lookalike poses, or inference time. Name the one you actually hit.
- User-study plan from `evaluation/user_study/protocol.md`.

## Demo

Live, ungraded, audience vote. Show the camera, the key, a repeated trial, and say out loud that the network is on the ESP32.

## Final

10 minutes, plus a YouTube link.

1. Problem and user
2. Architecture (`docs/architecture.md`)
3. Sensor pipeline
4. Model and the dataset you collected
5. Why 64×64, quadrant pooling, and int8 weights
6. Accuracy, latency, RAM, flash, power
7. User study: design, n, and the actual numbers
8. Failures you observed, separate from the risks listed before testing
9. Demo video
