# Dataset

Images in these folders are 64×64 grayscale PNGs captured by the ESP32, not phone photos. The collector asks the board for the same thumbnail the model classifies, so training and deployment see the same scaling.

```
model/dataset/POINT_UP/
model/dataset/POINT_DOWN/
model/dataset/THUMBS_UP/
model/dataset/OPEN_PALM/
model/dataset/NO_GESTURE/
```

Collect at least 40 images per class before training. Vary the person, the room, the light, the distance, and a small tilt. For `NO_GESTURE`, include an empty scene, a face, a fist, and a hand that is only partly in frame. Do not mirror the up and down classes. A vertical flip would swap those labels.

Quit `tools/serial_bridge.py` before collecting. Both open the serial port.

```bash
python tools/collect_dataset.py --label POINT_UP --count 40
```

Training refuses to run if any class has fewer than 20 images. It holds out about 20% per class and writes `model/deployment/metrics.json` plus a new `model_weights.cpp`. Flash the firmware again after that file changes. The accuracy in that JSON is not a user-study result.
