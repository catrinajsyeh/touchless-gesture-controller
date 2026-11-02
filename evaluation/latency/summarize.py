"""Summarize inference and end-to-end times from a bridge session log."""

import json
import statistics
import sys
from pathlib import Path


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def summarize(lines):
    inference = []
    e2e = []
    fired = 0
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("type") != "inference":
            continue
        if "inference_us" in payload:
            inference.append(payload["inference_us"] / 1000.0)
        if payload.get("fired") and payload.get("e2e_us"):
            e2e.append(payload["e2e_us"] / 1000.0)
            fired += 1
    return {
        "inference_samples": len(inference),
        "inference_ms_p50": percentile(inference, 0.50),
        "inference_ms_p95": percentile(inference, 0.95),
        "fired_keys": fired,
        "e2e_ms_p50": percentile(e2e, 0.50),
        "e2e_ms_p95": percentile(e2e, 0.95),
    }


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "evaluation/results/session.jsonl")
    if not path.exists():
        raise SystemExit(f"No log at {path}. Run tools/serial_bridge.py while using the board, then try again.")
    report = summarize(path.read_text(encoding="utf-8").splitlines())
    if report["inference_samples"] == 0:
        raise SystemExit("The log has no inference records yet.")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
