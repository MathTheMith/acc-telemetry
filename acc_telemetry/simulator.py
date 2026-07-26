"""Fake telemetry source used to test and demo the whole pipeline (recorder,
live view, track map) without ACC or a wheel plugged in.

Drives a virtual car around a made-up closed-loop circuit sized like a real
GT3 track (~4.2 km, ~16 corners of varying tightness), braking harder into
corners and applying throttle out of them. Each lap gets a random "trail
braking quality" that affects both how early it brakes and how much speed it
carries through the corner, so consecutive laps differ in both brake trace
*and* lap time -- not just a cosmetic difference.
"""
from __future__ import annotations

import random
import time
from typing import Optional

import numpy as np

from .sample import Sample

_STEP_M = 2.0  # uniform arc-length resampling step, in meters
_TRACK_LENGTH_M = 4200.0


def _build_raw_loop() -> np.ndarray:
    # Radial, multi-harmonic outline (fixed phases -> same demo circuit every
    # run) -- guaranteed to be a simple closed curve since radius is a
    # single-valued function of angle, unlike hand-picked control points.
    rng = np.random.default_rng(20260823)
    n = 16
    harmonics = [
        (2, 0.16, rng.uniform(0, 2 * np.pi)),
        (3, 0.24, rng.uniform(0, 2 * np.pi)),
        (5, 0.13, rng.uniform(0, 2 * np.pi)),
        (7, 0.07, rng.uniform(0, 2 * np.pi)),
    ]
    r0 = 260.0
    pts = []
    for i in range(n):
        theta = i / n * 2 * np.pi
        r = r0
        for k, amp, phase in harmonics:
            r += r0 * amp * np.sin(k * theta + phase)
        pts.append((np.cos(theta) * r, np.sin(theta) * r * 0.72))
    return np.array(pts)


def _catmull_rom_closed(pts: np.ndarray, samples_per_seg: int) -> np.ndarray:
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = pts[(i - 1) % n], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        t = np.linspace(0, 1, samples_per_seg, endpoint=False)
        t2, t3 = t * t, t * t * t
        seg = 0.5 * (
            (2 * p1)
            + (-p0 + p2) * t[:, None]
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2[:, None]
            + (-p0 + 3 * p1 - 3 * p2 + p3) * t3[:, None]
        )
        out.append(seg)
    return np.concatenate(out, axis=0)


class TrackModel:
    def __init__(self, target_length_m: float = _TRACK_LENGTH_M, step_m: float = _STEP_M):
        raw = _catmull_rom_closed(_build_raw_loop(), 40)
        seg = np.hypot(*(np.roll(raw, -1, axis=0) - raw).T)
        raw_cum = np.concatenate([[0.0], np.cumsum(seg)[:-1]])
        raw_len = float(seg.sum())
        scale = target_length_m / raw_len

        n_samp = int(target_length_m / step_m)
        target_raw = (np.arange(n_samp) * step_m) / scale
        seg_idx = np.searchsorted(raw_cum, target_raw, side="right") - 1
        seg_idx = np.clip(seg_idx, 0, len(raw) - 1)
        next_idx = (seg_idx + 1) % len(raw)
        seg_len = raw_cum[np.clip(seg_idx + 1, 0, len(raw_cum) - 1)] - raw_cum[seg_idx]
        frac = np.where(seg_len > 0, (target_raw - raw_cum[seg_idx]) / np.maximum(seg_len, 1e-9), 0.0)

        self.x = (raw[seg_idx, 0] + (raw[next_idx, 0] - raw[seg_idx, 0]) * frac) * scale
        self.z = (raw[seg_idx, 1] + (raw[next_idx, 1] - raw[seg_idx, 1]) * frac) * scale
        self.n = n_samp
        self.step = step_m
        self.length = n_samp * step_m

        heading = np.arctan2(np.roll(self.z, -1) - self.z, np.roll(self.x, -1) - self.x)
        dheading = np.angle(np.exp(1j * (np.roll(heading, -1) - heading)))
        window = max(1, round(18 / step_m))
        kernel = np.ones(2 * window + 1) / (2 * window + 1)
        dh_pad = np.concatenate([dheading[-window:], dheading, dheading[:window]])
        signed_curvature = np.convolve(dh_pad, kernel, mode="valid")
        curvature = np.abs(signed_curvature)
        curvature = curvature / (curvature.max() + 1e-9)
        self.curvature = curvature
        # positive = right-hand corner, negative = left-hand -- used to fake a
        # plausible steering trace (real sign convention TBD against real ACC
        # data, see acc_telemetry/reader.py)
        self.signed_curvature = signed_curvature / (np.abs(signed_curvature).max() + 1e-9)
        # 275 km/h flat out on the straights, down to ~75 km/h in the tightest hairpin
        self.target_speed = 275.0 - curvature * 200.0

    def index_at(self, norm_pos: float) -> int:
        return int((norm_pos % 1.0) * self.n) % self.n

    def point_at(self, dist_m: float):
        d = dist_m % self.length
        f = d / self.step
        i0 = int(f) % self.n
        i1 = (i0 + 1) % self.n
        frac = f - int(f)
        x = self.x[i0] + (self.x[i1] - self.x[i0]) * frac
        z = self.z[i0] + (self.z[i1] - self.z[i0]) * frac
        return x, z

    def speed_at(self, dist_m: float) -> float:
        d = dist_m % self.length
        f = d / self.step
        i0 = int(f) % self.n
        i1 = (i0 + 1) % self.n
        frac = f - int(f)
        return self.target_speed[i0] + (self.target_speed[i1] - self.target_speed[i0]) * frac

    def signed_curvature_at(self, dist_m: float) -> float:
        d = dist_m % self.length
        f = d / self.step
        i0 = int(f) % self.n
        i1 = (i0 + 1) % self.n
        frac = f - int(f)
        c0, c1 = self.signed_curvature[i0], self.signed_curvature[i1]
        return c0 + (c1 - c0) * frac


class SimulatedReader:
    def __init__(self):
        self.track = TrackModel()
        self._t0 = time.monotonic()
        self._last_t = self._t0
        self.pos_m = 0.0
        self.speed_kmh = 200.0
        self.completed_laps = 0
        self.lap_start_t = self._t0
        self.last_time_ms = 0
        self.best_time_ms = 0
        self._lap_quality = random.uniform(0.35, 0.9)
        self._brake_state = 0.0
        self._steer_state = 0.0
        self.current_sector_index = 0
        self.last_sector_time_ms = 0
        self._sector_start_t = self._t0

    def poll(self) -> Optional[Sample]:
        now = time.monotonic()
        dt = now - self._last_t
        if dt < (1.0 / 60.0):
            return None
        self._last_t = now

        # Lower quality -> brakes earlier (more lookahead) and leaves a bigger
        # margin through the corner (lower corner_mult); higher quality
        # brakes later and carries speed closer to the limit. Both compound
        # over ~16 corners into a real lap-time gap, not just a cosmetic
        # brake-trace difference.
        lookahead = 30.0 + (1.0 - self._lap_quality) * 90.0
        corner_mult = 0.87 + 0.15 * self._lap_quality

        target_now = self.track.speed_at(self.pos_m) * corner_mult
        target_ahead = self.track.speed_at(self.pos_m + lookahead) * corner_mult

        gas = 0.0
        if self.speed_kmh > target_ahead + 3:
            deficit = min(1.0, (self.speed_kmh - target_ahead) / 100.0)
            smoothing = 0.10 + 0.6 * self._lap_quality
            self._brake_state += (deficit - self._brake_state) * smoothing
            brake = max(0.0, min(1.0, self._brake_state))
        else:
            self._brake_state *= 0.55
            brake = max(0.0, self._brake_state)
            if self.speed_kmh < target_now - 2:
                gas = min(1.0, (target_now - self.speed_kmh) / 40.0 + 0.3)
            else:
                gas = 0.55

        accel_ms2 = gas * 6.0 - brake * 9.5 - 0.12
        self.speed_kmh = max(45.0, self.speed_kmh + accel_ms2 * dt * 3.6)
        prev_pos_m = self.pos_m
        raw_pos_m = self.pos_m + (self.speed_kmh / 3.6) * dt

        lap_wrapped = raw_pos_m >= self.track.length
        self.pos_m = raw_pos_m - self.track.length if lap_wrapped else raw_pos_m

        sector_bounds = (self.track.length / 3, self.track.length * 2 / 3)
        for b in sector_bounds:
            if prev_pos_m < b <= raw_pos_m:
                self.last_sector_time_ms = int((now - self._sector_start_t) * 1000)
                self.current_sector_index = (self.current_sector_index + 1) % 3
                self._sector_start_t = now
        if lap_wrapped:
            self.last_sector_time_ms = int((now - self._sector_start_t) * 1000)
            self.current_sector_index = 0
            self._sector_start_t = now

        norm_pos = self.pos_m / self.track.length
        x, z = self.track.point_at(self.pos_m)

        # Steering leads the curvature peak a little (turn-in before the
        # apex, like a real driver) and is smoothed rather than snapping
        # straight to target, for a plausible-looking trace -- not a real
        # physics model.
        target_steer = self.track.signed_curvature_at(self.pos_m + 8.0) * 5.0
        self._steer_state += (target_steer - self._steer_state) * 0.15

        current_time_ms = int((now - self.lap_start_t) * 1000)

        if lap_wrapped:
            self.completed_laps += 1
            self.last_time_ms = current_time_ms
            if self.best_time_ms == 0 or self.last_time_ms < self.best_time_ms:
                self.best_time_ms = self.last_time_ms
            self.lap_start_t = now
            current_time_ms = 0
            self._lap_quality = max(0.15, min(0.98, self._lap_quality + random.uniform(-0.25, 0.25)))

        return Sample(
            t=now - self._t0,
            gas=gas,
            brake=brake,
            steer=self._steer_state,
            speed_kmh=self.speed_kmh,
            gear=4,
            rpm=int(4000 + self.speed_kmh * 20),
            x=float(x),
            z=float(z),
            norm_pos=norm_pos,
            completed_laps=self.completed_laps,
            current_time_ms=current_time_ms,
            last_time_ms=self.last_time_ms,
            best_time_ms=self.best_time_ms,
            current_sector_index=self.current_sector_index,
            last_sector_time_ms=self.last_sector_time_ms,
            is_valid_lap=True,
            in_pit=False,
            in_pit_lane=False,
            status="ACC_LIVE",
            track="Circuit demo (simulateur)",
            car_model="GT3 demo",
        )

    def close(self) -> None:
        pass
