"""Save 64x64 grayscale frames from the ESP32 into the training folders.

Quit the serial bridge first. Both programs open the same COM port.
Images are the board's own scaled frames, so training sees the same pixels
the model will see later. This script does not label by looking at the image.
You choose the folder by holding that pose.
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import serial
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.ports import choose
from tools.protocol import BAUD, LABELS


def read_messages(link, seconds):
    deadline = time.time() + seconds
    buffer = b""
    while time.time() < deadline:
        buffer += link.read(1024)
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            text = line.decode("utf-8", errors="ignore").strip()
            if not text.startswith("{"):
                continue
            try:
                yield json.loads(text)
            except json.JSONDecodeError:
                continue


def send(link, payload):
    link.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")


def one_frame(link):
    send(link, {"cmd": "frame"})
    for message in read_messages(link, 8):
        if message.get("type") == "frame" and message.get("fmt", "gray") == "gray":
            return message
    raise TimeoutError("The board did not return a frame. Check the camera ribbon and the serial baud.")


def save_frame(message, path):
    raw = base64.b64decode(message["data"])
    width = int(message["w"])
    height = int(message["h"])
    if len(raw) != width * height:
        raise RuntimeError("Frame size did not match the grayscale buffer.")
    Image.frombytes("L", (width, height), raw).save(path)


def main():
    parser = argparse.ArgumentParser(description="Collect gesture frames from the ESP32")
    parser.add_argument("--label", required=True, choices=LABELS)
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--port", default=None)
    parser.add_argument("--delay", type=float, default=0.45)
    args = parser.parse_args()
    port = choose(args.port)
    if port is None:
        raise SystemExit("Pass --port COMx. No single ESP32 serial port was found.")
    folder = ROOT / "model" / "dataset" / args.label
    folder.mkdir(parents=True, exist_ok=True)
    existing = len(list(folder.glob("*.png")))
    print(f"Opening {port}. Hold {args.label} in front of the camera.")
    print("Keys are paused while this runs.")
    link = serial.Serial(port, BAUD, timeout=0.2)
    time.sleep(0.3)
    try:
        send(link, {"cmd": "suspend", "value": 1})
        for step in range(3, 0, -1):
            print(step)
            time.sleep(1)
        for index in range(args.count):
            message = one_frame(link)
            path = folder / f"{args.label.lower()}_{existing + index + 1:04d}.png"
            save_frame(message, path)
            print(f"saved {index + 1}/{args.count}  {path.name}")
            time.sleep(args.delay)
    finally:
        try:
            send(link, {"cmd": "suspend", "value": 0})
        except serial.SerialException:
            pass
        link.close()
    print(f"Done. {args.label} now has {len(list(folder.glob('*.png')))} images.")


if __name__ == "__main__":
    main()
