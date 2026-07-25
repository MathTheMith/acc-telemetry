from dataclasses import dataclass


@dataclass
class Sample:
    """One telemetry frame, normalized to a shape independent of the source
    (real ACC shared memory or the simulator)."""

    t: float                # seconds since app start
    gas: float               # 0..1
    brake: float             # 0..1
    steer: float              # radians
    speed_kmh: float
    gear: int
    rpm: int
    x: float                  # world position, meters
    z: float                  # world position, meters (x/z = top-down plane)
    norm_pos: float            # 0..1 position along the track spline
    completed_laps: int
    current_time_ms: int
    last_time_ms: int
    best_time_ms: int
    current_sector_index: int
    last_sector_time_ms: int
    is_valid_lap: bool
    in_pit: bool
    in_pit_lane: bool
    status: str
    track: str
    car_model: str
