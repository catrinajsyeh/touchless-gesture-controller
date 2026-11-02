"""Serve the latest ESP32 telemetry to the dashboard.

The bridge only forwards JSON the board already computed. It does not
classify images. Stop this process before collect_dataset.py, because both
need the same serial port.
"""

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import serial

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
}
lock = threading.Lock()
serial_port = None
stop = False


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
                    if kind == "frame":
                        with lock:
                            state["frame"] = payload
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
            }
        self._send(200, snapshot)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/command":
            self._send(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            command = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "detail": "bad_json"})
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
    server = ThreadingHTTPServer((BRIDGE_HOST, BRIDGE_PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop = True
        server.shutdown()


if __name__ == "__main__":
    main()
