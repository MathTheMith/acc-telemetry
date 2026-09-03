import csv
import json

from acc_telemetry.lap_recorder import Lap
from acc_telemetry.session_store import SessionStore, format_lap_time


def test_format_lap_time():
    assert format_lap_time(0) == "--:--.---"
    assert format_lap_time(-5) == "--:--.---"
    assert format_lap_time(65_123) == "1:05.123"


def make_lap(number=1, lap_time_ms=90_500, valid=True, sectors_ms=None) -> Lap:
    return Lap(
        number=number, lap_time_ms=lap_time_ms, valid=valid,
        sectors_ms=sectors_ms or [30_000, 30_000, 30_500],
        t=[0.0, 0.5, 1.0], gas=[0.0, 0.5, 1.0], brake=[1.0, 0.0, 0.0],
        speed_kmh=[100.0, 150.0, 200.0], steer=[0.0, 0.1, 0.0],
        x=[0.0, 1.0, 2.0], z=[0.0, 0.0, 0.0], norm_pos=[0.0, 0.5, 0.99],
    )


def test_save_lap_writes_a_csv_with_one_row_per_sample(tmp_path):
    store = SessionStore(str(tmp_path), track="Spa", car="GT3 demo")
    path = store.save_lap(make_lap())

    assert path.exists()
    with path.open() as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["t", "gas", "brake", "speed_kmh", "steer", "x", "z", "norm_pos"]
    assert len(rows) == 1 + 3  # header + 3 samples


def test_save_lap_updates_session_summary_with_best_lap(tmp_path):
    store = SessionStore(str(tmp_path), track="Spa", car="GT3 demo")
    store.save_lap(make_lap(number=1, lap_time_ms=95_000))
    store.save_lap(make_lap(number=2, lap_time_ms=90_000))
    store.save_lap(make_lap(number=3, lap_time_ms=93_000, valid=False))

    summary = json.loads((store.dir / "session.json").read_text())
    assert summary["track"] == "Spa"
    assert summary["car"] == "GT3 demo"
    assert len(summary["laps"]) == 3
    assert summary["best_lap"]["number"] == 2
    assert summary["best_lap"]["lap_time_ms"] == 90_000


def test_update_meta_rewrites_summary_once_known(tmp_path):
    store = SessionStore(str(tmp_path), track="unknown", car="unknown")
    store.save_lap(make_lap())
    store.update_meta("Spa", "GT3 demo")

    summary = json.loads((store.dir / "session.json").read_text())
    assert summary["track"] == "Spa"
    assert summary["car"] == "GT3 demo"
