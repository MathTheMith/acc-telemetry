import importlib

import pytest


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    import app as backend_app
    importlib.reload(backend_app)
    return backend_app.app.test_client()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}


def test_create_list_and_get_lap(client):
    payload = {
        "track": "Spa", "car": "GT3 demo", "number": 1, "lap_time_ms": 90_000,
        "valid": True, "sectors_ms": [30_000, 30_000, 30_000],
        "samples": [{"speed_kmh": 200.0}, {"speed_kmh": 250.0}],
    }
    res = client.post("/api/laps", json=payload)
    assert res.status_code == 201
    lap_id = res.get_json()["id"]

    res = client.get("/api/laps")
    laps = res.get_json()
    assert len(laps) == 1
    assert laps[0]["track"] == "Spa"
    assert laps[0]["top_speed_kmh"] == 250.0

    res = client.get(f"/api/laps/{lap_id}")
    assert res.status_code == 200
    detail = res.get_json()
    assert len(detail["samples"]) == 2
    assert detail["sectors_ms"] == [30_000, 30_000, 30_000]


def test_missing_track_and_car_default_to_unknown(client):
    res = client.post("/api/laps", json={"lap_time_ms": 90_000})
    lap_id = res.get_json()["id"]
    detail = client.get(f"/api/laps/{lap_id}").get_json()
    assert detail["track"] == "unknown"
    assert detail["car"] == "unknown"


def test_get_missing_lap_returns_404(client):
    assert client.get("/api/laps/999").status_code == 404


def test_delete_lap(client):
    res = client.post("/api/laps", json={"track": "Spa", "car": "GT3", "lap_time_ms": 1000})
    lap_id = res.get_json()["id"]

    assert client.delete(f"/api/laps/{lap_id}").status_code == 204
    assert client.get(f"/api/laps/{lap_id}").status_code == 404


def test_filter_by_track_and_car(client):
    client.post("/api/laps", json={"track": "Spa", "car": "GT3", "lap_time_ms": 1000})
    client.post("/api/laps", json={"track": "Monza", "car": "GT3", "lap_time_ms": 2000})

    res = client.get("/api/laps?track=Spa")
    assert [l["track"] for l in res.get_json()] == ["Spa"]

    res = client.get("/api/tracks")
    assert sorted(t["track"] for t in res.get_json()) == ["Monza", "Spa"]
