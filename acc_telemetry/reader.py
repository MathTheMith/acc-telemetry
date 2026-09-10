"""Live reader backed by ACC's shared memory.

Only works on Windows, with Assetto Corsa Competizione running, and requires
the `pyaccsharedmemory` package (Windows-only). Layout/field names follow the
community-documented ACC Shared Memory spec used by
https://github.com/rrennoir/PyAccSharedMemory
"""
from __future__ import annotations

import time
from typing import Optional

from .sample import Sample

try:
    from pyaccsharedmemory import accSharedMemory
    HAVE_ACC_SHARED_MEMORY = True
except ImportError:
    HAVE_ACC_SHARED_MEMORY = False


class AccReader:
    def __init__(self):
        if not HAVE_ACC_SHARED_MEMORY:
            raise RuntimeError(
                "pyaccsharedmemory is not available. This library only "
                "works on Windows (pip install pyaccsharedmemory)."
            )
        self._asm = accSharedMemory()
        self._t0 = time.monotonic()

    def poll(self) -> Optional[Sample]:
        """Returns a new Sample if ACC produced a new physics frame since the
        last call, otherwise None (no new data yet -- e.g. ACC not running,
        paused, or simply no new frame since the last poll)."""
        sm = self._asm.read_shared_memory()
        if sm is None:
            return None

        g = sm.Graphics
        p = sm.Physics
        s = sm.Static

        x = z = 0.0
        try:
            idx = list(g.car_id).index(g.player_car_id)
            coord = g.car_coordinates[idx]
            x, z = coord.x, coord.z
        except (ValueError, IndexError):
            pass

        return Sample(
            t=time.monotonic() - self._t0,
            gas=p.gas,
            brake=p.brake,
            steer=p.steer_angle,
            speed_kmh=p.speed_kmh,
            gear=p.gear,
            rpm=p.rpm,
            x=x,
            z=z,
            norm_pos=g.normalized_car_position,
            completed_laps=g.completed_lap,
            current_time_ms=g.current_time,
            last_time_ms=g.last_time,
            best_time_ms=g.best_time,
            current_sector_index=g.current_sector_index,
            last_sector_time_ms=g.last_sector_time,
            is_valid_lap=g.is_valid_lap,
            in_pit=g.is_in_pit,
            in_pit_lane=g.is_in_pit_lane,
            status=g.status.name,
            track=s.track.split("\x00", 1)[0],
            car_model=s.car_model.split("\x00", 1)[0],
        )

    def close(self) -> None:
        self._asm.close()
