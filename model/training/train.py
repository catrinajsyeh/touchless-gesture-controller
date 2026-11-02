"""Train the gesture CNN and, for a real dataset, export it to the firmware."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from model.training.export_weights import dequantize, write_cpp
from model.training.tiny_cnn import INPUT_SIZE, TinyCnn, normalize_uint8

ARCH = json.loads((Path(__file__).parent / "architecture.json").read_text(encoding="utf-8"))
LABELS = ARCH["classes"]


def load_split(dataset, seed=7, test_fraction=0.2, minimum=20):
    rng = np.random.default_rng(seed)
    train_x, train_y, test_x, test_y = [], [], [], []
    counts = {}
    for label, name in enumerate(LABELS):
        paths = sorted((dataset / name).glob("*.png")) + sorted((dataset / name).glob("*.jpg"))
        counts[name] = len(paths)
        if len(paths) < minimum:
            raise SystemExit(
                f"{name} has {len(paths)} images. Collect at least {minimum} with tools/collect_dataset.py."
            )
        order = rng.permutation(len(paths))
        test_n = max(1, int(round(len(paths) * test_fraction)))
        for index, path_index in enumerate(order):
            image = Image.open(paths[path_index]).convert("L").resize((INPUT_SIZE, INPUT_SIZE))
            pixels = np.asarray(image, dtype=np.uint8)
            if index < test_n:
                test_x.append(pixels)
                test_y.append(label)
            else:
                train_x.append(pixels)
                train_y.append(label)
    return (
        np.stack(train_x),
        np.array(train_y, dtype=np.int64),
        np.stack(test_x),
        np.array(test_y, dtype=np.int64),
        counts,
    )


def synthetic(per_class=80, test_per_class=20, seed=3):
    rng = np.random.default_rng(seed)
    train_x, train_y, test_x, test_y = [], [], [], []

    def draw(label, augment):
        image = rng.normal(38, 10, size=(INPUT_SIZE, INPUT_SIZE))
        if label == 0:
            image[6:42, 29:35] = 230
        elif label == 1:
            image[24:60, 29:35] = 230
        elif label == 2:
            image[8:26, 38:56] = 220
            image[22:38, 42:50] = 70
        elif label == 3:
            for finger in range(5):
                x = 10 + finger * 10
                image[14:46, x : x + 3] = 225
            image[40:52, 8:56] = 200
        if augment:
            image = np.roll(image, shift=(int(rng.integers(-3, 4)), int(rng.integers(-3, 4))), axis=(0, 1))
            image = image * float(rng.uniform(0.8, 1.2))
        return np.clip(image, 0, 255).astype(np.uint8)

    for label in range(len(LABELS)):
        for _ in range(per_class):
            train_x.append(draw(label, True))
            train_y.append(label)
        for _ in range(test_per_class):
            test_x.append(draw(label, True))
            test_y.append(label)
    return np.stack(train_x), np.array(train_y), np.stack(test_x), np.array(test_y)


def batch_images(images):
    return normalize_uint8(images)[:, None, :, :]


def run_training(train_x, train_y, test_x, test_y, epochs, lr, seed):
    rng = np.random.default_rng(seed)
    net = TinyCnn(rng)
    batch = 16
    for epoch in range(epochs):
        order = rng.permutation(len(train_x))
        losses = []
        for start in range(0, len(order), batch):
            idx = order[start : start + batch]
            loss, grads, _ = net.loss_and_grad(batch_images(train_x[idx]), train_y[idx])
            net.sgd(grads, lr=lr)
            losses.append(loss)
        pred, _ = net.predict(batch_images(test_x))
        accuracy = float((pred == test_y).mean())
        print(f"epoch {epoch + 1}/{epochs}  loss {np.mean(losses):.3f}  test_acc {accuracy:.3f}")
    return net


def confusion(y_true, y_pred):
    matrix = np.zeros((len(LABELS), len(LABELS)), dtype=np.int64)
    for truth, guess in zip(y_true, y_pred):
        matrix[int(truth), int(guess)] += 1
    return matrix


def report_metrics(y_true, y_pred):
    matrix = confusion(y_true, y_pred)
    per_class = {}
    none = len(LABELS) - 1
    negatives = max(1, int(np.sum(y_true == none)))
    for index, name in enumerate(LABELS):
        tp = int(matrix[index, index])
        support = int(matrix[index].sum())
        predicted = int(matrix[:, index].sum())
        per_class[name] = {
            "precision": tp / predicted if predicted else 0.0,
            "recall": tp / support if support else 0.0,
            "support": support,
        }
        if index != none:
            false_positives = int(np.sum((y_pred == index) & (y_true == none)))
            per_class[name]["false_positive_rate_on_no_gesture"] = false_positives / negatives
    return {
        "accuracy": float((y_true == y_pred).mean()),
        "confusion_matrix": matrix.tolist(),
        "labels": LABELS,
        "per_class": per_class,
    }


def dequantized_net(net, info):
    names = ["w1", "b1", "w2", "b2", "w3", "b3", "wd", "bd"]
    for name, quantized, scale in zip(names, info["quantized"], info["scales"]):
        setattr(net, name, dequantize(quantized, scale))


def main():
    parser = argparse.ArgumentParser(description="Train the on-device gesture model")
    parser.add_argument("--dataset", type=Path, default=ROOT / "model" / "dataset")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--lr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--synthetic", action="store_true", help="Check the trainer on shapes. Does not touch firmware.")
    args = parser.parse_args()

    if args.synthetic:
        train_x, train_y, test_x, test_y = synthetic()
        net = run_training(train_x, train_y, test_x, test_y, epochs=max(4, min(args.epochs, 8)), lr=args.lr, seed=args.seed)
        pred, _ = net.predict(batch_images(test_x))
        metrics = report_metrics(test_y, pred)
        print(json.dumps({"synthetic_accuracy": metrics["accuracy"]}, indent=2))
        if metrics["accuracy"] < 0.9:
            raise SystemExit("Synthetic check failed. The trainer did not separate the toy shapes.")
        return

    train_x, train_y, test_x, test_y, counts = load_split(args.dataset, seed=args.seed)
    print("images", counts)
    net = run_training(train_x, train_y, test_x, test_y, epochs=args.epochs, lr=args.lr, seed=args.seed)
    pred, _ = net.predict(batch_images(test_x))
    metrics = report_metrics(test_y, pred)
    info = write_cpp(
        ROOT / "firmware" / "src" / "gesture_recognition" / "model_weights.cpp",
        net.pack(),
        trained=True,
        domain="gestures",
    )
    dequantized_net(net, info)
    q_pred, _ = net.predict(batch_images(test_x))
    quantized_metrics = report_metrics(test_y, q_pred)
    deployment = ROOT / "model" / "deployment"
    deployment.mkdir(parents=True, exist_ok=True)
    np.savez(deployment / "weights.npz", **{name: value for name, value in net.parameters()})
    summary = {
        "counts": counts,
        "float32": metrics,
        "int8_dequantized": quantized_metrics,
        "float_weight_bytes": info["float_bytes"],
        "int8_weight_bytes": info["int8_bytes"],
        "checksum": info["checksum"],
        "note": "Accuracy is on the held-out images from this dataset, not on the user study.",
    }
    (deployment / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    results = ROOT / "evaluation" / "results"
    results.mkdir(parents=True, exist_ok=True)
    (results / "latest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"accuracy": metrics["accuracy"], "int8_accuracy": quantized_metrics["accuracy"]}, indent=2))


if __name__ == "__main__":
    main()
