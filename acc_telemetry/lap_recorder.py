"""Splits the incoming sample stream into laps.

The boundary is detected on `normalized_car_position` wrapping from close to
1.0 back down to close to 0.0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .sample import Sample

WRAP_HIGH = 0.9
WRAP_LOW = 0.15


@dataclass
class Lap:
    number: int = 0
    lap_time_ms: int = 0
    valid: bool = True
    t: List[float] = field(default_factory=list)
    gas: List[float] = field(default_factory=list)
    brake: List[float] = field(default_factory=list)
    speed_kmh: List[float] = field(default_factory=list)
    steer: List[float] = field(default_factory=list)
    x: List[float] = field(default_factory=list)
    z: List[float] = field(default_factory=list)
    norm_pos: List[float] = field(default_factory=list)


class LapRecorder:
    def __init__(self):
        self._buffer = Lap()
        self._prev_norm_pos: Optional[float] = None
        self._last_valid_flag = True
        self._lap_counter = 0
        self.completed_laps: List[Lap] = []

    def add_sample(self, s: Sample) -> Optional[Lap]:
        finished_lap = None

        if self._prev_norm_pos is not None:
            wrapped = self._prev_norm_pos > WRAP_HIGH and s.norm_pos < WRAP_LOW
            if wrapped:
                finished_lap = self._finalize_lap(s)

        self._buffer.t.append(s.t)
        self._buffer.gas.append(s.gas)
        self._buffer.brake.append(s.brake)
        self._buffer.speed_kmh.append(s.speed_kmh)
        self._buffer.steer.append(s.steer)
        self._buffer.x.append(s.x)
        self._buffer.z.append(s.z)
        self._buffer.norm_pos.append(s.norm_pos)

        self._last_valid_flag = s.is_valid_lap
        self._prev_norm_pos = s.norm_pos
        return finished_lap

    def _finalize_lap(self, s: Sample) -> Lap:
        self._lap_counter += 1
        finished = self._buffer
        finished.number = self._lap_counter
        finished.lap_time_ms = s.last_time_ms
        finished.valid = self._last_valid_flag
        self.completed_laps.append(finished)
        self._buffer = Lap()
        return finished

    @property
    def current_lap(self) -> Lap:
        return self._buffer
