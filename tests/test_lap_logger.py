import json

from acc_telemetry.lap_logger import NEW_SESSION_AFTER_S, LapLogger
from acc_telemetry.lap_recorder import MIN_SAMPLES_FOR_LAP
from acc_telemetry.sample import Sample


def make_sample(**overrides) -> Sample:
    defaults = dict(
        t=0.0, gas=0.0, brake=0.0, steer=0.0, speed_kmh=200.0, gear=4, rpm=6000,
        x=0.0, z=0.0, norm_pos=0.0, completed_laps=0, current_time_ms=0,
        last_time_ms=0, best_time_ms=0, current_sector_index=0,
        last_sector_time_ms=0, is_valid_lap=True, in_pit=False, in_pit_lane=False,
        status="ACC_LIVE", track="spa", car_model="ferrari_296_gt3",
    )
    defaults.update(overrides)
    return Sample(**defaults)


class FakeUploads(list):
    def __call__(self, lap, track, car):
        self.append((lap.number, track, car))


def drive_lap(logger, start=0.0, lap_time_ms=90_000, **overrides):
    """One full lap of samples ending with the wrap; returns the clock after it."""
    n = MIN_SAMPLES_FOR_LAP + 5
    for i in range(n):
        logger.feed(make_sample(t=start + i, norm_pos=0.05 + (i / n) * 0.9, **overrides), start + i)
    logger.feed(make_sample(t=start + n, norm_pos=0.02, last_time_ms=lap_time_ms, **overrides), start + n)
    return start + n + 1


def session_dirs(tmp_path):
    return sorted(p for p in tmp_path.iterdir() if p.is_dir())


def test_laps_are_saved_and_uploaded(tmp_path):
    uploads = FakeUploads()
    logger = LapLogger(str(tmp_path), upload=uploads)
    clock = drive_lap(logger)
    drive_lap(logger, start=clock, lap_time_ms=89_000)

    assert logger.laps_saved == 2
    assert uploads == [(1, "spa", "ferrari_296_gt3"), (2, "spa", "ferrari_296_gt3")]
    [session] = session_dirs(tmp_path)
    summary = json.loads((session / "session.json").read_text())
    assert summary["track"] == "spa"
    assert summary["best_lap"]["lap_time_ms"] == 89_000


def test_no_folder_until_a_lap_is_finished(tmp_path):
    logger = LapLogger(str(tmp_path), upload=FakeUploads())
    for i in range(10):
        logger.feed(make_sample(t=i, norm_pos=i / 100), i)
    assert session_dirs(tmp_path) == []


def test_replay_and_menus_are_not_recorded(tmp_path):
    uploads = FakeUploads()
    logger = LapLogger(str(tmp_path), upload=uploads)
    drive_lap(logger, status="ACC_REPLAY")
    drive_lap(logger, status="ACC_PAUSE")
    assert uploads == []
    assert session_dirs(tmp_path) == []


def test_changing_car_starts_a_new_session(tmp_path):
    uploads = FakeUploads()
    logger = LapLogger(str(tmp_path), upload=uploads)
    clock = drive_lap(logger)
    drive_lap(logger, start=clock, car_model="porsche_992_gt3_r")

    assert uploads == [(1, "spa", "ferrari_296_gt3"), (1, "spa", "porsche_992_gt3_r")]


def test_long_gap_starts_a_new_session(tmp_path):
    uploads = FakeUploads()
    logger = LapLogger(str(tmp_path), upload=uploads)
    clock = drive_lap(logger)
    drive_lap(logger, start=clock + NEW_SESSION_AFTER_S + 1)

    assert [number for number, _, _ in uploads] == [1, 1]
