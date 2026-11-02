"""Describe the user-study sheet. It does not invent rows."""

import csv
import sys
from collections import defaultdict
from pathlib import Path

PATH = Path(__file__).with_name("responses.csv")


def main():
    with PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("responses.csv has no sessions yet. Run the protocol before analyzing it.")
    people = {row["participant"] for row in rows}
    if len(people) < 5:
        print(f"Warning: {len(people)} participant(s). The course asks for at least 5.")
    grouped = defaultdict(list)
    for row in rows:
        try:
            grouped[row["interface"]].append(float(row["time_s"]))
        except ValueError:
            raise SystemExit(f"Bad time_s for participant {row['participant']}.")
    for interface, times in grouped.items():
        mean = sum(times) / len(times)
        print(f"{interface}: n={len(times)} mean_time_s={mean:.2f}")
    print("These are descriptive means only.")


if __name__ == "__main__":
    main()
