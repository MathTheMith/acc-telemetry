"""Persists each completed lap to disk as soon as it finishes, so a session
is never lost even if the app is closed or crashes mid-session. Post-session
analysis can reload `session.json` + the per-lap CSVs from any machine."""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Optional

from .lap_recorder import Lap


def format_lap_time(ms: int) -> str:
    if ms <= 0:
        return "--:--.---"
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    return f"{minutes}:{seconds:06.3f}"


class SessionStore:
    def __init__(self, base_dir: str, track: str = "unknown", car: str = "unknown"):
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        safe_track = (track or "unknown").strip().replace(" ", "_") or "unknown"
        self.dir = Path(base_dir) / f"{stamp}_{safe_track}"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.track = track
        self.car = car
        self._laps_meta = []

    def update_meta(self, track: str, car: str) -> None:
        if track != self.track or car != self.car:
            self.track = track
            self.car = car
            self._write_summary()

    def save_lap(self, lap: Lap) -> Path:
        time_tag = format_lap_time(lap.lap_time_ms).replace(":", "m").replace(".", "-")
        fname = f"lap_{lap.number:03d}_{'valid' if lap.valid else 'invalid'}_{time_tag}s.csv"
        path = self.dir / fname

        with path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["t", "gas", "brake", "speed_kmh", "steer", "x", "z", "norm_pos"])
            for row in zip(
                lap.t, lap.gas, lap.brake, lap.speed_kmh, lap.steer, lap.x, lap.z, lap.norm_pos
            ):
                writer.writerow(row)

        self._laps_meta.append({
            "number": lap.number,
            "lap_time_ms": lap.lap_time_ms,
            "lap_time_str": format_lap_time(lap.lap_time_ms),
            "valid": lap.valid,
            "sectors_ms": lap.sectors_ms,
            "file": path.name,
        })
        self._write_summary()
        return path
