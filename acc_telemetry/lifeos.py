"""Optional: also send each lap's result to a Life OS instance (personal
dashboard with an AI chat that follows pace and consistency over time).

Only the result leaves the machine: track, car, lap time and whether the lap
was valid. No telemetry trace. Disabled unless both env vars are set:

    LIFEOS_URL=https://<your Life OS>/api/sim-laps
    LIFEOS_TOKEN=<its TELEMETRY_TOKEN>

The uid ("<session folder>/<lap number>") makes it idempotent: re-sending a
lap, or importing old sessions with scripts/import_to_lifeos.py, never
creates duplicates.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import List, Optional


def lap_result(session_id: str, number: int, track: str, car: str,
               lap_time_ms: int, valid: bool, driven_at: datetime) -> dict:
    return {
        "uid": f"{session_id}/{number}",
        "track": track,
        "car": car,
        "lapTimeMs": int(lap_time_ms),
        "valid": bool(valid),
        "drivenAt": driven_at.astimezone().isoformat(),
    }


def send_lap_results(laps: List[dict], timeout: float = 10.0) -> Optional[dict]:
    """Returns Life OS's answer ({received, inserted, rejected}), or None if
    it's not configured or unreachable (the lap is still safe on disk)."""
    url = os.environ.get("LIFEOS_URL", "").strip()
    token = os.environ.get("LIFEOS_TOKEN", "").strip()
    if not url or not token or not laps:
        return None
    req = urllib.request.Request(
        url,
        data=json.dumps({"laps": laps}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"[lifeos] Life OS unreachable ({e}) -- lap kept locally only.")
        return None
