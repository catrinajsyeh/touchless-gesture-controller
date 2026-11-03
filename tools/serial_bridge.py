"""Serve the ESP32 camera to the dashboard and save training photos.

The class hand tracker finds the hand. The gesture itself is the model
running on the board. Stop this process before collect_dataset.py, because
both need the same serial port.
"""

import base64
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.dataset_service import counts, predict_gray, save_gray, save_image, start_train, train_status
from tools.ports import candidates, choose
from tools.protocol import BAUD, BRIDGE_HOST, BRIDGE_PORT

RESULTS = ROOT / "evaluation" / "results" / "latest.json"
LOG_PATH = ROOT / "evaluation" / "results" / "session.jsonl"

state = {
    "serial_open": False,
    "port": None,
    "error": None,
    "status": None,
    "inference": None,
    "frame": None,
    "activity": [],
    "logs": [],
    "jpeg_seq": 0,
    "hand": None,
    "hand_crop": None,
    "hand_seq": 0,
    "keys_armed": False,
    "capturing": False,
    "saw_neutral": True,
    "last_key": 0,
}

KEYS = {
    "POINT_UP": "up",
    "POINT_DOWN": "down",
    "THUMBS_UP": "l",
    "OPEN_PALM": "space",
}
lock = threading.Lock()
serial_port = None
stop = False
gray_seq = 0
gray_event = threading.Event()
serial_cmd_lock = threading.Lock()


def remember(kind, payload):
    with lock:
        state[kind] = payload
        if kind == "inference":
            decision = payload.get("decision")
            if decision == "neutral":
                return
            previous = state["activity"][0] if state["activity"] else None
            if (
                previous
                and not payload.get("fired")
                and previous.get("gesture") == payload.get("gesture")
                and previous.get("decision") == decision
            ):
                return
            state["activity"].insert(
                0,
                {
                    "t": time.time(),
                    "gesture": payload.get("gesture"),
                    "key": payload.get("key") or "",
                    "decision": decision,
                    "fired": payload.get("fired"),
                    "confidence": payload.get("confidence"),
                },
            )
            del state["activity"][40:]
        elif kind == "key":
            state["activity"].insert(
                0,
                {
                    "t": time.time(),
                    "gesture": payload.get("gesture"),
                    "key": payload.get("key") or "",
                    "decision": "manual",
                    "fired": True,
                    "confidence": None,
                },
            )
            del state["activity"][40:]


def reader(port_name):
    global serial_port, stop
    while not stop:
        try:
            link = serial.Serial(port_name, BAUD, timeout=1)
        except serial.SerialException as exc:
            with lock:
                state["serial_open"] = False
                state["error"] = str(exc)
            time.sleep(2)
            continue
        serial_port = link
        with lock:
            state["serial_open"] = True
            state["port"] = port_name
            state["error"] = None
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        buffer = b""
        try:
            while not stop:
                chunk = link.read(512)
                if not chunk:
                    continue
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    text = line.decode("utf-8", errors="ignore").strip()
                    if not text.startswith("{"):
                        continue
                    try:
                        payload = json.loads(text)
                    except json.JSONDecodeError:
                        continue
                    kind = payload.get("type")
                    if kind == "frame" and payload.get("fmt") == "jpeg":
                        with lock:
                            state["jpeg_seq"] += 1
                            state["frame"] = payload
                    elif kind == "frame":
                        global gray_seq
                        with lock:
                            state["gray"] = payload
                            gray_seq += 1
                            gray_event.set()
                    elif kind in ("status", "inference", "key"):
                        remember(kind, payload)
                    elif kind in ("log", "boot", "ack"):
                        with lock:
                            state["logs"].insert(0, {"t": time.time(), "payload": payload})
                            del state["logs"][8:]
                    if kind != "frame":
                        with LOG_PATH.open("a", encoding="utf-8") as handle:
                            handle.write(text + "\n")
        except serial.SerialException as exc:
            with lock:
                state["serial_open"] = False
                state["error"] = str(exc)
        finally:
            try:
                link.close()
            except serial.SerialException:
                pass
            serial_port = None
        time.sleep(1)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] != "/state":
            self._send(404, {"error": "not_found"})
            return
        evaluation = None
        if RESULTS.exists():
            try:
                evaluation = json.loads(RESULTS.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                evaluation = None
        with lock:
            snapshot = {
                "bridge": True,
                "serial_open": state["serial_open"],
                "port": state["port"],
                "error": state["error"],
                "status": state["status"],
                "inference": state["inference"],
                "frame": state["frame"],
                "activity": list(state["activity"]),
                "logs": list(state["logs"]),
                "evaluation": evaluation,
                "ports": [{"device": device, "description": description} for _, device, description in candidates()],
                "dataset": counts(),
                "train": train_status(),
                "hand": state["hand"],
            }
        self._send(200, snapshot)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            command = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "detail": "bad_json"})
            return
        if path == "/capture":
            label = command.get("label")
            count = int(command.get("count") or 1)
            count = max(1, min(count, 40))
            try:
                saved = capture_photos(label, count)
            except Exception as exc:
                self._send(409, {"ok": False, "detail": str(exc)})
                return
            self._send(200, {"ok": True, "saved": saved, "dataset": counts()})
            return
        if path == "/train":
            started = start_train()
            status = train_status()
            self._send(200 if started or status["status"] == "running" else 400, {"ok": started, **status})
            return
        if path == "/keys":
            with lock:
                state["keys_armed"] = bool(command.get("value"))
                if not state["keys_armed"]:
                    state["saw_neutral"] = True
            self._send(200, {"ok": True})
            return
        if path == "/predict":
            try:
                result = predict_live()
            except Exception as exc:
                self._send(409, {"ok": False, "detail": str(exc)})
                return
            self._send(200, result)
            return
        if path != "/command":
            self._send(404, {"error": "not_found"})
            return
        link = serial_port
        if link is None or not getattr(link, "is_open", False):
            self._send(409, {"ok": False, "detail": "serial_closed"})
            return
        line = json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n"
        try:
            link.write(line)
        except serial.SerialException as exc:
            self._send(409, {"ok": False, "detail": str(exc)})
            return
        self._send(200, {"ok": True})


def write_command(command):
    link = serial_port
    if link is None or not getattr(link, "is_open", False):
        raise RuntimeError("serial_closed")
    link.write(json.dumps(command, separators=(",", ":")).encode("utf-8") + b"\n")


def wait_gray(timeout=3):
    global gray_seq
    with lock:
        seen = gray_seq
        gray_event.clear()
    write_command({"cmd": "frame"})
    deadline = time.time() + timeout
    while time.time() < deadline:
        if gray_event.wait(0.05):
            with lock:
                if gray_seq > seen and state.get("gray"):
                    return state["gray"]
            gray_event.clear()
    raise TimeoutError("The board did not send a training frame.")


def wait_hand(seen, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with lock:
            seq = state.get("hand_seq", 0)
            hand = state.get("hand") or {}
            crop = state.get("hand_crop")
        if seq > seen and hand.get("hand") and crop is not None:
            return crop.copy(), seq
        time.sleep(0.05)
    raise TimeoutError(
        "No hand in the picture. Hold your hand close to the lens, with your face farther back, and try again."
    )


def capture_photos(label, count):
    if label == "NO_GESTURE":
        return capture_scene(count)
    saved = []
    with serial_cmd_lock:
        with lock:
            state["capturing"] = True
        write_command({"cmd": "suspend", "value": 1})
        try:
            for _ in range(count):
                with lock:
                    hand = state.get("hand") or {}
                    box = hand.get("box")
                    present = bool(hand.get("hand")) and box
                if not present:
                    raise TimeoutError("No hand in the picture. Put your hand in front of the lens, closer than your face.")
                write_command({"cmd": "crop", "hand": 1, "x": box["x"], "y": box["y"], "w": box["w"], "h": box["h"]})
                saved.append(save_gray(wait_gray(), label))
                time.sleep(0.2)
        finally:
            with lock:
                state["capturing"] = False
            try:
                write_command({"cmd": "suspend", "value": 0})
            except Exception:
                pass
    return saved


def capture_scene(count):
    saved = []
    with serial_cmd_lock:
        with lock:
            state["capturing"] = True
        write_command({"cmd": "suspend", "value": 1})
        write_command({"cmd": "crop", "hand": 0, "x": 0, "y": 0, "w": 1, "h": 1})
        try:
            for _ in range(count):
                saved.append(save_gray(wait_gray(), "NO_GESTURE"))
                time.sleep(0.3)
        finally:
            with lock:
                state["capturing"] = False
            try:
                write_command({"cmd": "suspend", "value": 0})
            except Exception:
                pass
    return saved


def maybe_send_key(label):
    now = time.time()
    with lock:
        if state.get("capturing") or not state.get("keys_armed"):
            return
        ble = (state.get("status") or {}).get("ble")
        if ble != "connected" or label not in KEYS:
            return
        if not state.get("saw_neutral", True):
            return
        if now - state.get("last_key", 0) < 0.7:
            return
        state["saw_neutral"] = False
        state["last_key"] = now
    try:
        with serial_cmd_lock:
            write_command({"cmd": "keytest", "key": KEYS[label]})
    except Exception:
        with lock:
            state["saw_neutral"] = True


def watch_hands():
    try:
        from tools.hand_gestures import analyze_jpeg, tracker
        tracker()
    except Exception as exc:
        with lock:
            state["error"] = f"Hand tracker failed to start: {exc}"
        print(f"Hand tracker failed: {exc}")
        return
    print("Hand tracker ready")
    seen = 0
    while not stop:
        with lock:
            seq = state.get("jpeg_seq", 0)
            frame = state.get("frame")
        if seq == seen or not frame or not frame.get("data"):
            time.sleep(0.04)
            continue
        try:
            found = analyze_jpeg(base64.b64decode(frame["data"]))
        except Exception as exc:
            print(f"Hand tracker: {exc}")
            seen = seq
            time.sleep(0.1)
            continue
        if found is None:
            seen = seq
            continue
        encoded = base64.b64encode(found["jpeg"]).decode("ascii")
        box = found.get("box") or {"x": 0, "y": 0, "w": 1, "h": 1}
        command = {
            "cmd": "crop",
            "hand": 1 if found["hand"] else 0,
            "x": box["x"],
            "y": box["y"],
            "w": box["w"],
            "h": box["h"],
        }
        with lock:
            if state.get("jpeg_seq") == seq:
                updated = dict(frame)
                updated["data"] = encoded
                state["frame"] = updated
            state["hand"] = {
                "hand": found["hand"],
                "box": box,
            }
            state["hand_crop"] = None if found["crop"] is None else found["crop"].copy()
            state["hand_seq"] += 1
        seen = seq
        if serial_cmd_lock.acquire(blocking=False):
            try:
                write_command(command)
            except Exception:
                pass
            finally:
                serial_cmd_lock.release()


def predict_live():
    with serial_cmd_lock:
        gray = wait_gray()
    return predict_gray(gray)


def main():
    global stop
    port_name = choose(sys.argv[1] if len(sys.argv) > 1 else None)
    if port_name is None:
        print("No ESP32 serial port was selected.")
        for _, device, description in candidates():
            print(f"  {device}  {description}")
        print("Pass the COM port: python tools/serial_bridge.py COM5")
        raise SystemExit(1)
    print(f"Bridge on http://{BRIDGE_HOST}:{BRIDGE_PORT}  serial {port_name} @ {BAUD}")
    threading.Thread(target=reader, args=(port_name,), daemon=True).start()
    threading.Thread(target=watch_hands, daemon=True).start()
    server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop = True
        server.shutdown()


if __name__ == "__main__":
    main()
