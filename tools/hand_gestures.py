"""Read the four poses from a hand skeleton.

This uses the same MediaPipe hand model as the course workshop. The tracker
returns 21 points on the hand, so the face and the room are not part of the
decision.
"""

from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

MODEL = Path(
    r"C:\Users\Catrina\Desktop\ECE209AS-InteractiveSystem-Workshop-main"
    r"\ECE209AS-InteractiveSystem-Workshop-main"
    r"\Demo1_HandInteractionPlayground\assets\hand_landmarker.task"
)

NAMES = {
    "POINT_UP": "Index up",
    "POINT_DOWN": "Index down",
    "THUMBS_UP": "Thumbs up",
    "OPEN_PALM": "Open palm",
    "NO_GESTURE": "No gesture",
}

CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20),
)

_landmarker = None


def tracker():
    global _landmarker
    if _landmarker is None:
        if not MODEL.exists():
            raise FileNotFoundError(f"Hand model not found: {MODEL}")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        _landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
    return _landmarker


def _distance(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def _extended(hand, tip, pip, mcp):
    tip_from_wrist = _distance(hand[tip], hand[0])
    pip_from_wrist = _distance(hand[pip], hand[0])
    return tip_from_wrist > pip_from_wrist * 1.12 and _distance(hand[tip], hand[mcp]) > _distance(hand[pip], hand[mcp])


def classify_landmarks(hand):
    """Return the pose name and a confidence from the 21 landmark points."""
    index = _extended(hand, 8, 6, 5)
    middle = _extended(hand, 12, 10, 9)
    ring = _extended(hand, 16, 14, 13)
    pinky = _extended(hand, 20, 18, 17)
    folded = not middle and not ring and not pinky
    thumb_out = _distance(hand[4], hand[5]) > _distance(hand[3], hand[5]) * 1.2
    if index and middle and ring and pinky:
        return "OPEN_PALM", 0.92
    if thumb_out and folded and not index and hand[4].y < hand[2].y:
        return "THUMBS_UP", 0.9
    if index and folded and hand[8].y < hand[5].y - 0.04:
        return "POINT_UP", 0.9
    if index and folded and hand[8].y > hand[5].y + 0.04:
        return "POINT_DOWN", 0.9
    return "NO_GESTURE", 0.2


def features_from_hand(hand):
    xs = np.array([point.x for point in hand], dtype=np.float32)
    ys = np.array([point.y for point in hand], dtype=np.float32)
    xy = np.stack([xs, ys], axis=1)
    wrist = xy[0]
    rel = xy - wrist
    scale = float(np.linalg.norm(rel, axis=1).max())
    if scale < 1e-6:
        scale = 1.0
    return (rel / scale).reshape(-1).astype(np.float32)


def _crop(image, hand):
    height, width = image.shape[:2]
    xs = [point.x * width for point in hand]
    ys = [point.y * height for point in hand]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    pad = max(20, int(span * 0.45))
    x0 = max(0, int(min(xs)) - pad)
    y0 = max(0, int(min(ys)) - pad)
    x1 = min(width, int(max(xs)) + pad)
    y1 = min(height, int(max(ys)) + pad)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None, span / max(width, height)
    gray = cv2.cvtColor(image[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA), span / max(width, height)


def _draw(image, hand):
    height, width = image.shape[:2]
    points = [(int(point.x * width), int(point.y * height)) for point in hand]
    for start, end in CONNECTIONS:
        cv2.line(image, points[start], points[end], (80, 220, 120), 2)
    for point in points:
        cv2.circle(image, point, 4, (255, 255, 255), -1)


def analyze_jpeg(jpeg_bytes):
    image = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return None
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    result = tracker().detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
    label = "NO_GESTURE"
    confidence = 0.0
    present = False
    crop = None
    box = None
    features = None
    if result.hand_landmarks:
        present = True
        hand = result.hand_landmarks[0]
        label, confidence = classify_landmarks(hand)
        features = features_from_hand(hand)
        crop, span = _crop(image, hand)
        if span < 0.18:
            label, confidence = "NO_GESTURE", 0.2
        _draw(image, hand)
        xs = [point.x for point in hand]
        ys = [point.y for point in hand]
        pad_x = max(0.04, (max(xs) - min(xs)) * 0.35)
        pad_y = max(0.04, (max(ys) - min(ys)) * 0.35)
        x0 = max(0.0, min(xs) - pad_x)
        y0 = max(0.0, min(ys) - pad_y)
        x1 = min(1.0, max(xs) + pad_x)
        y1 = min(1.0, max(ys) + pad_y)
        box = {"x": round(x0, 3), "y": round(y0, 3), "w": round(x1 - x0, 3), "h": round(y1 - y0, 3)}
    else:
        box = None
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    pose = NAMES[label] if label != "NO_GESTURE" else ("Hand seen" if present else "No hand")
    return {
        "label": label,
        "name": pose,
        "confidence": confidence,
        "hand": present and crop is not None,
        "jpeg": encoded.tobytes() if ok else jpeg_bytes,
        "crop": crop,
        "box": box,
        "features": None if features is None else [round(float(v), 4) for v in features],
    }


class _Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _hand():
    return [_Point(0.5, 0.7) for _ in range(21)]


def _self_check():
    hand = _hand()
    hand[5], hand[6], hand[7], hand[8] = _Point(0.55, 0.55), _Point(0.55, 0.4), _Point(0.55, 0.3), _Point(0.55, 0.16)
    hand[9], hand[10], hand[12] = _Point(0.64, 0.55), _Point(0.66, 0.62), _Point(0.62, 0.68)
    hand[13], hand[14], hand[16] = _Point(0.72, 0.58), _Point(0.74, 0.64), _Point(0.7, 0.7)
    hand[17], hand[18], hand[20] = _Point(0.78, 0.62), _Point(0.8, 0.68), _Point(0.76, 0.72)
    hand[1], hand[2], hand[3], hand[4] = _Point(0.42, 0.64), _Point(0.4, 0.6), _Point(0.42, 0.58), _Point(0.46, 0.6)
    assert classify_landmarks(hand)[0] == "POINT_UP", classify_landmarks(hand)

    down = _hand()
    down[0] = _Point(0.5, 0.3)
    down[5], down[6], down[8] = _Point(0.55, 0.45), _Point(0.55, 0.6), _Point(0.55, 0.86)
    down[9], down[10], down[12] = _Point(0.64, 0.46), _Point(0.62, 0.4), _Point(0.6, 0.36)
    down[13], down[14], down[16] = _Point(0.7, 0.48), _Point(0.68, 0.42), _Point(0.66, 0.38)
    down[17], down[18], down[20] = _Point(0.76, 0.5), _Point(0.74, 0.44), _Point(0.72, 0.4)
    down[2], down[3], down[4] = _Point(0.4, 0.4), _Point(0.42, 0.42), _Point(0.46, 0.44)
    assert classify_landmarks(down)[0] == "POINT_DOWN", classify_landmarks(down)

    thumb = _hand()
    thumb[1], thumb[2], thumb[3], thumb[4] = _Point(0.42, 0.62), _Point(0.4, 0.5), _Point(0.42, 0.38), _Point(0.46, 0.22)
    thumb[5] = _Point(0.58, 0.58)
    thumb[9], thumb[10], thumb[12] = _Point(0.64, 0.58), _Point(0.66, 0.64), _Point(0.62, 0.7)
    thumb[13], thumb[14], thumb[16] = _Point(0.7, 0.6), _Point(0.72, 0.66), _Point(0.68, 0.72)
    thumb[17], thumb[18], thumb[20] = _Point(0.76, 0.62), _Point(0.78, 0.68), _Point(0.74, 0.74)
    thumb[6], thumb[8] = _Point(0.58, 0.64), _Point(0.56, 0.7)
    assert classify_landmarks(thumb)[0] == "THUMBS_UP", classify_landmarks(thumb)

    palm = _hand()
    palm[5], palm[6], palm[8] = _Point(0.42, 0.5), _Point(0.4, 0.34), _Point(0.38, 0.16)
    palm[9], palm[10], palm[12] = _Point(0.52, 0.48), _Point(0.52, 0.3), _Point(0.52, 0.1)
    palm[13], palm[14], palm[16] = _Point(0.62, 0.5), _Point(0.64, 0.34), _Point(0.66, 0.16)
    palm[17], palm[18], palm[20] = _Point(0.72, 0.54), _Point(0.76, 0.4), _Point(0.8, 0.22)
    assert classify_landmarks(palm)[0] == "OPEN_PALM", classify_landmarks(palm)
    print("pose checks passed")


if __name__ == "__main__":
    _self_check()
