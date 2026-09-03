import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from acc_telemetry.lap_recorder import Lap
from acc_telemetry.uploader import LapUploader


def make_lap() -> Lap:
    return Lap(
        number=1, lap_time_ms=90_000, valid=True, sectors_ms=[30_000, 30_000, 30_000],
        t=[0.0, 1.0], gas=[0.5, 1.0], brake=[0.0, 0.0], speed_kmh=[150.0, 200.0],
        steer=[0.0, 0.0], x=[0.0, 1.0], z=[0.0, 0.0], norm_pos=[0.0, 0.5],
    )


class _CapturingHandler(BaseHTTPRequestHandler):
    captured = None

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _CapturingHandler.captured = {
            "payload": json.loads(body) if body else None,
        }
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # keep test output quiet


def run_capturing_server():
    server = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_upload_success_posts_the_lap_payload():
    server = run_capturing_server()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/laps"
        uploader = LapUploader(url=url)
        ok = uploader.upload(make_lap(), track="Spa", car="GT3 demo")
        assert ok is True
        assert _CapturingHandler.captured["payload"]["track"] == "Spa"
        assert _CapturingHandler.captured["payload"]["lap_time_ms"] == 90_000
        assert len(_CapturingHandler.captured["payload"]["samples"]) == 2
    finally:
        server.shutdown()


def test_upload_returns_false_when_server_unreachable():
    # Bind then immediately close a socket to get a port nothing listens on.
    probe = HTTPServer(("127.0.0.1", 0), _CapturingHandler)
    closed_port = probe.server_port
    probe.server_close()

    uploader = LapUploader(url=f"http://127.0.0.1:{closed_port}/api/laps", timeout=1.0)
    assert uploader.upload(make_lap(), track="Spa", car="GT3 demo") is False
