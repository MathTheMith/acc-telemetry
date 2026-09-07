"""Best-effort push of a finished lap to the Apex Trace web dashboard.

Fire-and-forget: if the server isn't reachable, this just logs and moves on
-- the lap is still safe on disk via SessionStore, so nothing is lost, and
the live app never depends on the server to keep working.

The target defaults to a server running on the same machine (server/app.py
directly), but the dashboard is typically deployed on a VPS instead (see
docker-compose.yml) -- point this at it with the ACC_SERVER_URL env var,
e.g. ACC_SERVER_URL=http://<VPS_IP>:8081/api/laps

If the server has an API_KEY configured (see backend/app.py), set the
matching ACC_API_KEY env var here so uploads aren't rejected with 401.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .lap_recorder import Lap

DEFAULT_URL = os.environ.get("ACC_SERVER_URL", "http://127.0.0.1:5000/api/laps")


class LapUploader:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 3.0):
        self.url = url
        self.timeout = timeout
        self.api_key = os.environ.get("ACC_API_KEY", "").strip()

    def upload(self, lap: Lap, track: str, car: str) -> bool:
        payload = {
            "track": track,
            "car": car,
            "number": lap.number,
            "lap_time_ms": lap.lap_time_ms,
            "valid": lap.valid,
            "sectors_ms": lap.sectors_ms,
            "samples": [
                {
                    "t": t, "gas": g, "brake": b, "speed_kmh": sp,
                    "x": x, "z": z, "steer": st, "norm_pos": np_,
                }
                for t, g, b, sp, x, z, st, np_ in zip(
                    lap.t, lap.gas, lap.brake, lap.speed_kmh, lap.x, lap.z,
                    lap.steer, lap.norm_pos,
                )
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        req = urllib.request.Request(self.url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout):
                pass
            return True
        except (urllib.error.URLError, OSError) as e:
            print(f"[uploader] Server unreachable ({e}) -- lap kept in CSV only.")
            return False
