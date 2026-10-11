"""One-off: send the result of every lap already saved in sessions/ to Life OS
(track, car, lap time, valid or not -- nothing else).

    set LIFEOS_URL=https://<your Life OS>/api/sim-laps
    set LIFEOS_TOKEN=<its TELEMETRY_TOKEN>
    python scripts/import_to_lifeos.py [sessions_dir]

Safe to re-run: laps already in Life OS are skipped.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from acc_telemetry.lifeos import lap_result, send_lap_results  # noqa: E402

BATCH = 1000


def collect(sessions_dir: Path) -> list:
    laps = []
    for summary_path in sorted(sessions_dir.glob("*/session.json")):
        session_id = summary_path.parent.name
        try:
            started = datetime.strptime(session_id[:19], "%Y-%m-%d_%H-%M-%S")
            summary = json.loads(summary_path.read_text())
        except (ValueError, OSError) as e:
            print(f"skipped {session_id}: {e}")
            continue
        # Only the session start is on disk: rebuild each lap's time of day
        # from the lap times before it.
        driven_at = started
        for lap in sorted(summary.get("laps", []), key=lambda l: l["number"]):
            driven_at += timedelta(milliseconds=lap["lap_time_ms"])
            laps.append(lap_result(
                session_id, lap["number"], summary.get("track", "unknown"),
                summary.get("car", "unknown"), lap["lap_time_ms"], lap["valid"], driven_at,
            ))
    return laps


def main() -> None:
    sessions_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "sessions")
    laps = collect(sessions_dir)
    print(f"{len(laps)} laps found in {sessions_dir}")
    inserted = 0
    for i in range(0, len(laps), BATCH):
        answer = send_lap_results(laps[i:i + BATCH], timeout=60)
        if answer is None:
            sys.exit("Stopped: set LIFEOS_URL and LIFEOS_TOKEN, and check Life OS is reachable.")
        inserted += answer.get("inserted", 0)
        if answer.get("rejected"):
            print(f"{answer['rejected']} laps rejected (incomplete data)")
    print(f"done: {inserted} new laps in Life OS ({len(laps) - inserted} already there or rejected)")


if __name__ == "__main__":
    main()
