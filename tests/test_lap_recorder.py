from acc_telemetry.lap_recorder import MAX_LAP_TIME_MS, MIN_SAMPLES_FOR_LAP, LapRecorder
from acc_telemetry.sample import Sample


def make_sample(**overrides) -> Sample:
    defaults = dict(
        t=0.0, gas=0.0, brake=0.0, steer=0.0, speed_kmh=200.0, gear=4, rpm=6000,
        x=0.0, z=0.0, norm_pos=0.0, completed_laps=0, current_time_ms=0,
        last_time_ms=0, best_time_ms=0, current_sector_index=0,
        last_sector_time_ms=0, is_valid_lap=True, in_pit=False, in_pit_lane=False,
        status="ACC_LIVE", track="Spa", car_model="GT3 demo",
    )
    defaults.update(overrides)
    return Sample(**defaults)


def drive_lap(recorder, n=MIN_SAMPLES_FOR_LAP + 5, is_valid_lap=True, **wrap_kwargs):
    """Feeds `n` samples spanning norm_pos 0.05 -> 0.95, then wraps back to
    ~0.0 with the given overrides on the wrapping sample (e.g. last_time_ms,
    in_pit). `is_valid_lap` applies to the in-progress samples, matching
    LapRecorder's own behaviour of taking the validity flag from the last
    sample recorded *before* the wrap, not from the wrap sample itself.
    Returns whatever add_sample returns for that wrapping sample."""
    for i in range(n):
        pos = 0.05 + (i / n) * 0.9
        sector = 0 if pos < 0.33 else (1 if pos < 0.66 else 2)
        recorder.add_sample(make_sample(
            t=float(i), norm_pos=pos, current_sector_index=sector, is_valid_lap=is_valid_lap
        ))
    return recorder.add_sample(make_sample(t=float(n), norm_pos=0.02, current_sector_index=0, **wrap_kwargs))


def test_wrap_finishes_a_lap_with_the_reported_time():
    rec = LapRecorder()
    lap = drive_lap(rec, last_time_ms=90_123)
    assert lap is not None
    assert lap.number == 1
    assert lap.lap_time_ms == 90_123
    assert lap.valid is True
    assert rec.completed_laps == [lap]


def test_too_few_samples_does_not_finish_a_lap():
    rec = LapRecorder()
    lap = drive_lap(rec, n=5)  # well under MIN_SAMPLES_FOR_LAP
    assert lap is None
    assert rec.completed_laps == []


def test_wrap_while_in_pit_is_ignored():
    rec = LapRecorder()
    lap = drive_lap(rec, in_pit=True)
    assert lap is None
    assert rec.completed_laps == []


def test_lap_timeline_is_rebased_to_start_at_zero():
    rec = LapRecorder()
    # Drive with a session clock that doesn't start at 0.
    for i in range(MIN_SAMPLES_FOR_LAP + 5):
        pos = 0.05 + (i / (MIN_SAMPLES_FOR_LAP + 5)) * 0.9
        rec.add_sample(make_sample(t=100.0 + i, norm_pos=pos))
    lap = rec.add_sample(make_sample(t=200.0, norm_pos=0.02, last_time_ms=42_000))
    assert lap is not None
    assert lap.t[0] == 0.0
    assert lap.t == sorted(lap.t)


def test_best_lap_ignores_invalid_laps():
    rec = LapRecorder()
    drive_lap(rec, last_time_ms=95_000, is_valid_lap=True)
    drive_lap(rec, last_time_ms=90_000, is_valid_lap=False)
    drive_lap(rec, last_time_ms=93_000, is_valid_lap=True)

    assert [l.lap_time_ms for l in rec.completed_laps] == [95_000, 90_000, 93_000]
    assert [l.valid for l in rec.completed_laps] == [True, False, True]
    best = rec.best_lap
    assert best is not None
    assert best.lap_time_ms == 93_000


def test_bogus_lap_time_over_an_hour_is_dropped():
    rec = LapRecorder()
    lap = drive_lap(rec, last_time_ms=MAX_LAP_TIME_MS + 1)
    assert lap is None
    assert rec.completed_laps == []


def test_sectors_are_dropped_when_not_exactly_three():
    rec = LapRecorder()
    n = MIN_SAMPLES_FOR_LAP + 5
    for i in range(n):
        pos = 0.05 + (i / n) * 0.9
        # 4 distinct sector indices instead of the usual 3 (e.g. Nurburgring
        # 24h reporting an extra split) -- sectors_ms ends up with 4 entries.
        sector = min(int(pos * 4), 3)
        rec.add_sample(make_sample(
            t=float(i), norm_pos=pos, current_sector_index=sector, last_sector_time_ms=1000
        ))
    lap = rec.add_sample(make_sample(t=float(n), norm_pos=0.02, current_sector_index=0, last_time_ms=90_000))
    assert lap is not None
    assert lap.sectors_ms == []


def test_best_lap_is_none_with_no_valid_laps():
    rec = LapRecorder()
    assert rec.best_lap is None
    drive_lap(rec, last_time_ms=90_000, is_valid_lap=False)
    assert rec.best_lap is None
