"""Best-effort push of a finished lap to the Apex Trace web dashboard."""
from __future__ import annotations

import json
import os
import urllib.request

from .lap_recorder import Lap

DEFAULT_URL = os.environ.get("ACC_SERVER_URL", "http://127.0.0.1:5000/api/laps")


class LapUploader:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 3.0):
        self.url = url
        self.timeout = timeout

    def upload(self, lap: Lap, track: str, car: str) -> bool:
        payload = {
            "track": track,
            "car": car,
            "number": lap.number,
            "lap_time_ms": lap.lap_time_ms,
            "valid": lap.valid,
            "samples": [
                {"t": t, "gas": g, "brake": b, "speed_kmh": sp, "x": x, "z": z}
                for t, g, b, sp, x, z in zip(
                    lap.t, lap.gas, lap.brake, lap.speed_kmh, lap.x, lap.z,
                )
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout):
            pass
        return True
