"""Colors a lap's path by pedal input, for the trail-braking track map.

Convention (standard in racing telemetry HUDs): green = throttle, red =
brake, gray = coasting. Point size also scales with pedal intensity so the
picture still reads if red/green is hard to distinguish.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np


def sample_color(gas: float, brake: float) -> Tuple[int, int, int]:
    gas = max(0.0, min(1.0, gas))
    brake = max(0.0, min(1.0, brake))

    if brake > 0.02:
        g_b = int(255 * (1 - brake) * 0.55)
        return (255, g_b, g_b)
    if gas > 0.02:
        r_b = int(255 * (1 - gas) * 0.55)
        return (r_b, 255, r_b)
    return (190, 190, 190)


def sample_size(gas: float, brake: float, base: float = 6.0) -> float:
    intensity = max(gas, brake)
    return base + intensity * 6.0


def lap_colors_and_sizes(gas: List[float], brake: List[float]):
    colors = np.array([sample_color(g, b) for g, b in zip(gas, brake)], dtype=np.uint8)
    sizes = np.array([sample_size(g, b) for g, b in zip(gas, brake)], dtype=float)
    return colors, sizes
