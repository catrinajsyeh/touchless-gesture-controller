# Deployment

`train.py` writes two artifacts:

- `firmware/src/gesture_recognition/model_weights.cpp` for the next flash. `kModelTrained` stays false in the copy that ships before you train, and the firmware will not emit gesture keys.
- `metrics.json` after a real training run: held-out accuracy for the float weights and for the int8 weights after they are expanded back to float, plus the weight sizes.

The checked-in weights are the untrained placeholder. Do not treat a synthetic training run as this file. `train.py --synthetic` only checks that the trainer can separate drawings, and it does not overwrite the firmware.
