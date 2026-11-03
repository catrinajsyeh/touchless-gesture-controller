"""Train a tiny MLP on hand landmarks, the same idea as the class tracker.

The laptop MediaPipe tracker finds the 21 points. This network learns which
pose those points mean. The weights are written for the ESP32.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT_CPP = ROOT / "firmware" / "src" / "gesture_recognition" / "landmark_weights.cpp"
OUT_H = ROOT / "firmware" / "src" / "gesture_recognition" / "landmark_weights.h"
OUT_NPZ = ROOT / "model" / "deployment" / "landmark_weights.npz"
OUT_METRICS = ROOT / "model" / "deployment" / "landmark_metrics.json"
LABELS = ["POINT_UP", "POINT_DOWN", "THUMBS_UP", "OPEN_PALM", "NO_GESTURE"]
HIDDEN = 24
INPUT = 42


def features_from_xy(xy: np.ndarray) -> np.ndarray:
    """xy shape (21, 2) in image coords. Return wrist-centered unit features."""
    wrist = xy[0]
    rel = xy - wrist
    scale = np.linalg.norm(rel, axis=1).max()
    if scale < 1e-6:
        scale = 1.0
    rel = rel / scale
    return rel.reshape(-1).astype(np.float32)


def template(label: str, rng: np.random.Generator) -> np.ndarray:
    pts = np.zeros((21, 2), dtype=np.float32)
    pts[0] = (0.5, 0.7)
    # default slightly curled fingers
    for mcp, tip, side in ((5, 8, -0.08), (9, 12, 0.0), (13, 16, 0.08), (17, 20, 0.16)):
        pts[mcp] = (0.5 + side, 0.55)
        pts[mcp + 1] = (0.5 + side, 0.58)
        pts[mcp + 2] = (0.5 + side, 0.62)
        pts[tip] = (0.5 + side, 0.66)
    pts[1] = (0.42, 0.62)
    pts[2] = (0.40, 0.58)
    pts[3] = (0.42, 0.55)
    pts[4] = (0.46, 0.57)

    if label == "POINT_UP":
        pts[5], pts[6], pts[7], pts[8] = (0.52, 0.52), (0.52, 0.38), (0.52, 0.26), (0.52, 0.12)
    elif label == "POINT_DOWN":
        pts[0] = (0.5, 0.28)
        pts[5], pts[6], pts[7], pts[8] = (0.52, 0.42), (0.52, 0.56), (0.52, 0.70), (0.52, 0.86)
        for mcp, tip, side in ((9, 12, 0.08), (13, 16, 0.14), (17, 20, 0.20)):
            pts[mcp] = (0.5 + side, 0.40)
            pts[tip] = (0.5 + side, 0.34)
    elif label == "THUMBS_UP":
        pts[1], pts[2], pts[3], pts[4] = (0.42, 0.58), (0.40, 0.44), (0.42, 0.30), (0.46, 0.16)
        pts[5] = (0.58, 0.56)
        for mcp, tip, side in ((9, 12, 0.08), (13, 16, 0.14), (17, 20, 0.20)):
            pts[mcp] = (0.58 + side, 0.58)
            pts[tip] = (0.58 + side, 0.70)
        pts[6], pts[7], pts[8] = (0.58, 0.62), (0.57, 0.66), (0.56, 0.70)
    elif label == "OPEN_PALM":
        for mcp, tip, side, height in (
            (5, 8, -0.12, 0.14),
            (9, 12, -0.02, 0.10),
            (13, 16, 0.08, 0.14),
            (17, 20, 0.18, 0.20),
        ):
            pts[mcp] = (0.5 + side, 0.50)
            pts[mcp + 1] = (0.5 + side, 0.34)
            pts[mcp + 2] = (0.5 + side, 0.22)
            pts[tip] = (0.5 + side, height)
        pts[1], pts[2], pts[3], pts[4] = (0.38, 0.58), (0.32, 0.50), (0.28, 0.42), (0.24, 0.34)
    else:
        # messy / ambiguous
        pts += rng.normal(0, 0.05, pts.shape).astype(np.float32)

    pts += rng.normal(0, 0.012, pts.shape).astype(np.float32)
    return pts


def make_dataset(n_per_class: int = 400):
    rng = np.random.default_rng(7)
    xs, ys = [], []
    for index, label in enumerate(LABELS):
        for _ in range(n_per_class):
            xs.append(features_from_xy(template(label, rng)))
            ys.append(index)
    x = np.stack(xs)
    y = np.array(ys, dtype=np.int64)
    order = rng.permutation(len(y))
    return x[order], y[order]


def one_hot(y, count):
    out = np.zeros((len(y), count), dtype=np.float32)
    out[np.arange(len(y)), y] = 1.0
    return out


def train(x, y, epochs=80, lr=0.08):
    rng = np.random.default_rng(3)
    w1 = rng.normal(0, 0.2, (INPUT, HIDDEN)).astype(np.float32)
    b1 = np.zeros(HIDDEN, dtype=np.float32)
    w2 = rng.normal(0, 0.2, (HIDDEN, len(LABELS))).astype(np.float32)
    b2 = np.zeros(len(LABELS), dtype=np.float32)
    split = int(len(y) * 0.8)
    x_train, y_train = x[:split], y[:split]
    x_val, y_val = x[split:], y[split:]
    for epoch in range(epochs):
        logits = x_train @ w1 + b1
        hidden = np.maximum(logits, 0)
        scores = hidden @ w2 + b2
        scores -= scores.max(axis=1, keepdims=True)
        exp = np.exp(scores)
        probs = exp / exp.sum(axis=1, keepdims=True)
        target = one_hot(y_train, len(LABELS))
        dlogits = (probs - target) / len(y_train)
        dw2 = hidden.T @ dlogits
        db2 = dlogits.sum(axis=0)
        dhidden = dlogits @ w2.T
        dhidden[logits <= 0] = 0
        dw1 = x_train.T @ dhidden
        db1 = dhidden.sum(axis=0)
        w2 -= lr * dw2
        b2 -= lr * db2
        w1 -= lr * dw1
        b1 -= lr * db1
        if (epoch + 1) % 20 == 0:
            pred = predict(x_val, w1, b1, w2, b2)
            print(f"epoch {epoch + 1} val_acc={float((pred == y_val).mean()):.3f}")
    return w1, b1, w2, b2


def predict(x, w1, b1, w2, b2):
    hidden = np.maximum(x @ w1 + b1, 0)
    scores = hidden @ w2 + b2
    return scores.argmax(axis=1)


def quantize(weights):
    scale = float(np.max(np.abs(weights)) / 127.0) or 1.0
    q = np.clip(np.round(weights / scale), -127, 127).astype(np.int8)
    return q, scale


def write_cpp(w1, b1, w2, b2, accuracy):
    qw1, s1 = quantize(w1)
    qb1, sb1 = quantize(b1)
    qw2, s2 = quantize(w2)
    qb2, sb2 = quantize(b2)
    checksum = int(np.sum(qw1.astype(np.int32)) + np.sum(qw2.astype(np.int32))) & 0xFFFFFFFF

    def array_text(values, cols=18):
        flat = values.reshape(-1)
        lines = []
        for i in range(0, len(flat), cols):
            chunk = ", ".join(str(int(v)) for v in flat[i : i + cols])
            lines.append("    " + chunk + ",")
        return "\n".join(lines)

    header = f"""#pragma once

#include <stdint.h>

extern const bool kLandmarkModelTrained;
extern const char kLandmarkModelDomain[];
extern const uint32_t kLandmarkModelChecksum;
extern const int kLandmarkInput;
extern const int kLandmarkHidden;
extern const int kLandmarkClasses;
extern const float kLandmarkW1Scale;
extern const float kLandmarkB1Scale;
extern const float kLandmarkW2Scale;
extern const float kLandmarkB2Scale;
extern const int8_t kLandmarkW1[];
extern const int8_t kLandmarkB1[];
extern const int8_t kLandmarkW2[];
extern const int8_t kLandmarkB2[];
"""
    source = f"""#include "gesture_recognition/landmark_weights.h"

// Generated by model/training/train_landmarks.py
// held-out accuracy {accuracy:.4f}

const bool kLandmarkModelTrained = true;
const char kLandmarkModelDomain[] = "landmark_gestures";
const uint32_t kLandmarkModelChecksum = {checksum}u;
const int kLandmarkInput = {INPUT};
const int kLandmarkHidden = {HIDDEN};
const int kLandmarkClasses = {len(LABELS)};
const float kLandmarkW1Scale = {s1:.8f}f;
const float kLandmarkB1Scale = {sb1:.8f}f;
const float kLandmarkW2Scale = {s2:.8f}f;
const float kLandmarkB2Scale = {sb2:.8f}f;

const int8_t kLandmarkW1[] = {{
{array_text(qw1)}
}};

const int8_t kLandmarkB1[] = {{
{array_text(qb1)}
}};

const int8_t kLandmarkW2[] = {{
{array_text(qw2)}
}};

const int8_t kLandmarkB2[] = {{
{array_text(qb2)}
}};
"""
    OUT_H.write_text(header, encoding="utf-8")
    OUT_CPP.write_text(source, encoding="utf-8")
    np.savez(OUT_NPZ, w1=w1, b1=b1, w2=w2, b2=b2, labels=np.array(LABELS))
    OUT_METRICS.write_text(json.dumps({"accuracy": accuracy, "labels": LABELS, "input": INPUT, "hidden": HIDDEN}, indent=2), encoding="utf-8")


def main():
    x, y = make_dataset()
    w1, b1, w2, b2 = train(x, y)
    pred = predict(x, w1, b1, w2, b2)
    accuracy = float((pred == y).mean())
    write_cpp(w1, b1, w2, b2, accuracy)
    print(json.dumps({"ok": True, "accuracy": accuracy, "weights": str(OUT_CPP)}))


if __name__ == "__main__":
    main()
