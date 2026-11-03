"""Save camera frames and train the gesture model for the simple dashboard."""

import base64
import json
import subprocess
import sys
import threading
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "model" / "dataset"
WEIGHTS = ROOT / "model" / "deployment" / "weights.npz"
LABELS = ["POINT_UP", "POINT_DOWN", "THUMBS_UP", "OPEN_PALM", "NO_GESTURE"]
MINIMUM = 20

_train_lock = threading.Lock()
_train = {"status": "idle", "message": "", "accuracy": None}
_net = None
_net_stamp = None


def counts():
    found = {}
    for name in LABELS:
        folder = DATASET / name
        found[name] = len(list(folder.glob("*.png"))) if folder.exists() else 0
    return found


def save_image(image, label):
    if label not in LABELS:
        raise ValueError("unknown label")
    gray = np.asarray(image, dtype=np.uint8)
    if gray.shape != (64, 64):
        raise ValueError("hand crop must be 64x64")
    folder = DATASET / label
    folder.mkdir(parents=True, exist_ok=True)
    number = len(list(folder.glob("*.png"))) + 1
    path = folder / f"{label.lower()}_{number:04d}.png"
    Image.fromarray(gray, mode="L").save(path)
    return path.name


def save_gray(message, label):
    if label not in LABELS:
        raise ValueError("unknown label")
    if message.get("fmt", "gray") != "gray":
        raise ValueError("expected a grayscale model frame")
    raw = base64.b64decode(message["data"])
    width = int(message["w"])
    height = int(message["h"])
    if len(raw) != width * height:
        raise ValueError("frame size did not match")
    folder = DATASET / label
    folder.mkdir(parents=True, exist_ok=True)
    number = len(list(folder.glob("*.png"))) + 1
    path = folder / f"{label.lower()}_{number:04d}.png"
    Image.frombytes("L", (width, height), raw).save(path)
    return path.name


def train_status():
    with _train_lock:
        return dict(_train)


def start_train():
    with _train_lock:
        if _train["status"] == "running":
            return False
        missing = [name for name, count in counts().items() if count < MINIMUM]
        if missing:
            _train["status"] = "error"
            _train["message"] = "Each pose needs at least 20 photos. Still short: " + ", ".join(missing)
            _train["accuracy"] = None
            return False
        _train["status"] = "running"
        _train["message"] = "Training on the saved photos."
        _train["accuracy"] = None
    threading.Thread(target=_run_train, daemon=True).start()
    return True


def _run_train():
    global _net, _net_stamp
    try:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "model" / "training" / "train.py"), "--dataset", str(DATASET)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "Training failed.").strip().splitlines()
            message = detail[-1] if detail else "Training failed."
            with _train_lock:
                _train["status"] = "error"
                _train["message"] = message
                _train["accuracy"] = None
            return
        accuracy = None
        for line in reversed((completed.stdout or "").splitlines()):
            line = line.strip()
            if line.startswith("{") and "accuracy" in line:
                accuracy = json.loads(line).get("accuracy")
                break
        with _train_lock:
            _train["status"] = "done"
            _train["accuracy"] = accuracy
            _train["message"] = "Training finished. Check uses these weights on the live picture. The chip itself updates after you flash the firmware."
        _net = None
        _net_stamp = None
    except Exception as exc:
        with _train_lock:
            _train["status"] = "error"
            _train["message"] = str(exc)
            _train["accuracy"] = None


def _load_net():
    global _net, _net_stamp
    if not WEIGHTS.exists():
        return None
    stamp = WEIGHTS.stat().st_mtime
    if _net is not None and _net_stamp == stamp:
        return _net
    sys.path.insert(0, str(ROOT))
    from model.training.tiny_cnn import TinyCnn

    data = np.load(WEIGHTS)
    net = TinyCnn(0)
    for name, _value in net.parameters():
        setattr(net, name, np.asarray(data[name], dtype=np.float32))
    _net = net
    _net_stamp = stamp
    return net


def predict_gray(message):
    net = _load_net()
    if net is None:
        return {"ok": False, "detail": "Train a model before checking it."}
    if message.get("fmt", "gray") != "gray":
        return {"ok": False, "detail": "The board did not send a model frame."}
    raw = base64.b64decode(message["data"])
    width = int(message["w"])
    height = int(message["h"])
    if width != 64 or height != 64 or len(raw) != width * height:
        return {"ok": False, "detail": "Model frame was not 64×64."}
    pixels = np.frombuffer(raw, dtype=np.uint8).reshape(1, 1, 64, 64)
    normalized = pixels.astype(np.float32) / 127.5 - 1.0
    choice, probs = net.predict(normalized)
    scores = [float(value) for value in probs[0]]
    index = int(choice[0])
    return {
        "ok": True,
        "label": LABELS[index],
        "confidence": scores[index],
        "scores": scores,
        "labels": LABELS,
    }
