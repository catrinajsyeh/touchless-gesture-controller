"""Confirm the vectorized conv matches the loop order used by the firmware."""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model.training.tiny_cnn import TinyCnn, forward_loops, softmax


def main():
    rng = np.random.default_rng(11)
    net = TinyCnn(rng)
    image = rng.normal(size=(1, 64, 64)).astype(np.float32)
    logits, _ = net.forward(image[:, None, :, :])
    loop_probs = forward_loops(image, net.pack())
    batch_probs = softmax(logits)[0]
    if not np.allclose(loop_probs, batch_probs, atol=1e-4, rtol=1e-4):
        print("max abs", float(np.max(np.abs(loop_probs - batch_probs))))
        raise SystemExit("forward mismatch")
    print("forward match", np.round(batch_probs, 4).tolist())


if __name__ == "__main__":
    main()
