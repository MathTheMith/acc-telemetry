import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from acc_telemetry.lap_recorder import Lap
from acc_telemetry.lifeos import lap_result, send_lap_results
from acc_telemetry.session_store import SessionStore
from scripts.import_to_lifeos import collect


def test_lap_result_holds_only_the_result():
    r = lap_result("2026-10-05_20-00-00_monza", 3, "monza", "ferrari_296_gt3", 101_234, False,
                   datetime(2026, 10, 5, 20, 5))
    assert set(r) == {"uid", "track", "car", "lapTimeMs", "valid", "drivenAt"}
    assert r["uid"] == "2026-10-05_20-00-00_monza/3"
    assert r["lapTimeMs"] == 101_234 and r["valid"] is False
    assert r["drivenAt"].startswith("2026-10-05T20:05:00")


def test_nothing_is_sent_when_not_configured(monkeypatch):
    monkeypatch.delenv("LIFEOS_URL", raising=False)
    monkeypatch.delenv("LIFEOS_TOKEN", raising=False)
    assert send_lap_results([{"uid": "x"}]) is None


def test_send_posts_the_laps_with_the_token(monkeypatch):
    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received["auth"] = self.headers["Authorization"]
            received["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = json.dumps({"received": 1, "inserted": 1, "rejected": 0}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    monkeypatch.setenv("LIFEOS_URL", f"http://127.0.0.1:{server.server_port}/api/sim-laps")
    monkeypatch.setenv("LIFEOS_TOKEN", "secret")

    answer = send_lap_results([{"uid": "a/1"}])
    server.server_close()
    assert answer == {"received": 1, "inserted": 1, "rejected": 0}
    assert received["auth"] == "Bearer secret"
    assert received["body"] == {"laps": [{"uid": "a/1"}]}


def test_import_rebuilds_laps_from_saved_sessions(tmp_path):
    store = SessionStore(str(tmp_path), track="monza", car="ferrari_296_gt3")
    for number, ms, valid in [(1, 101_000, True), (2, 100_000, False)]:
        store.save_lap(Lap(number=number, lap_time_ms=ms, valid=valid, t=[0.0], gas=[0.0], brake=[0.0],
                           speed_kmh=[0.0], steer=[0.0], x=[0.0], z=[0.0], norm_pos=[0.0]))

    laps = collect(tmp_path)
    assert [(l["uid"], l["lapTimeMs"], l["valid"]) for l in laps] == [
        (f"{store.dir.name}/1", 101_000, True),
        (f"{store.dir.name}/2", 100_000, False),
    ]
    assert laps[0]["track"] == "monza" and laps[0]["car"] == "ferrari_296_gt3"
    assert laps[0]["drivenAt"] < laps[1]["drivenAt"]
