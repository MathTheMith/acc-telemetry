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
