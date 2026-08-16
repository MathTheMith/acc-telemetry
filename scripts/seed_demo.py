"""Pushes a handful of demo laps to a running Apex Trace server, so the site
isn't empty while testing from a phone before the real desktop app/ACC is
available. Uses the same simulator + uploader code the real app uses.

Usage:
    python3 scripts/seed_demo.py [server_url]
    (default server_url: http://127.0.0.1:8081, the Nginx-exposed port)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from acc_telemetry.lap_recorder import LapRecorder
from acc_telemetry.simulator import SimulatedReader
from acc_telemetry.uploader import LapUploader


def run(server_url: str, track: str, car: str, n_laps: int) -> None:
    reader = SimulatedReader()
    recorder = LapRecorder()
    uploader = LapUploader(url=server_url.rstrip("/") + "/api/laps")

    n = 0
    start = time.time()
    while n < n_laps and time.time() - start < 90 * n_laps:
        s = reader.poll()
        if s is None:
            continue
        finished = recorder.add_sample(s)
        if finished:
            n += 1
            ok = uploader.upload(finished, track=track, car=car)
            print(f"lap {finished.number}: {finished.lap_time_ms} ms, sent={ok}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081"
    print(f"Sending demo laps to {url} ...")
    run(url, track="Nurburgring GP", car="Ferrari 296 GT3", n_laps=3)
    run(url, track="Spa demo", car="BMW M4 GT3", n_laps=2)
    print("Done.")
