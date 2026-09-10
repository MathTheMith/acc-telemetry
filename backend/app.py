"""Apex Trace API -- receives lap telemetry from the desktop app (wherever it
runs) and serves it back to the web dashboard (frontend/, behind Nginx).

Pure JSON API: the static dashboard itself is served by Nginx (see
frontend/), not by Flask -- mirrors the tennis site's split (Nginx serves the
SPA + proxies /api/* to this container, which is never exposed publicly on
its own).
"""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request

DB_PATH = Path(os.environ.get("DATABASE_PATH", "/data/telemetry.db"))

# Optional: set API_KEY to require a matching X-API-Key header on the
# write endpoints (create/delete). Reads stay open -- browsing the
# dashboard isn't sensitive, losing or forging laps is. Empty/unset
# disables auth entirely, so existing deployments keep working as-is.
API_KEY = os.environ.get("API_KEY", "").strip()

app = Flask(__name__)


def require_api_key(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if API_KEY and not hmac.compare_digest(request.headers.get("X-API-Key", ""), API_KEY):
            return jsonify({"error": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS laps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track TEXT NOT NULL,
            car TEXT NOT NULL,
            lap_number INTEGER,
            recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
            lap_time_ms INTEGER NOT NULL,
            valid INTEGER NOT NULL DEFAULT 1,
            top_speed_kmh REAL,
            sectors_ms TEXT,
            samples_json TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def lap_summary_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "track": row["track"],
        "car": row["car"],
        "lap_number": row["lap_number"],
        "recorded_at": row["recorded_at"],
        "lap_time_ms": row["lap_time_ms"],
        "valid": bool(row["valid"]),
        "top_speed_kmh": row["top_speed_kmh"],
        "sectors_ms": json.loads(row["sectors_ms"]) if row["sectors_ms"] else [],
    }


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/laps", methods=["GET"])
def list_laps():
    track = request.args.get("track")
    car = request.args.get("car")
    query = "SELECT * FROM laps"
    conditions, params = ["valid = 1"], []
    if track:
        conditions.append("track = ?")
        params.append(track)
    if car:
        conditions.append("car = ?")
        params.append(car)
    query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY recorded_at DESC"

    rows = get_db().execute(query, params).fetchall()
    return jsonify([lap_summary_row(r) for r in rows])


@app.route("/api/tracks", methods=["GET"])
def list_tracks():
    rows = get_db().execute(
        "SELECT DISTINCT track, car FROM laps WHERE valid = 1 ORDER BY track, car"
    ).fetchall()
    return jsonify([{"track": r["track"], "car": r["car"]} for r in rows])


@app.route("/api/laps", methods=["POST"])
@require_api_key
def create_lap():
    payload = request.get_json(force=True)
    samples = payload.get("samples", [])
    top_speed = max((s.get("speed_kmh", 0) for s in samples), default=0)

    db = get_db()
    cur = db.execute(
        """INSERT INTO laps (track, car, lap_number, lap_time_ms, valid, top_speed_kmh, sectors_ms, samples_json)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            payload.get("track", "unknown"),
            payload.get("car", "unknown"),
            payload.get("number"),
            payload.get("lap_time_ms", 0),
            1 if payload.get("valid", True) else 0,
            top_speed,
            json.dumps(payload.get("sectors_ms", [])),
            json.dumps(samples),
        ),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/api/laps/<int:lap_id>", methods=["GET"])
def get_lap(lap_id: int):
    row = get_db().execute("SELECT * FROM laps WHERE id = ?", (lap_id,)).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    data = lap_summary_row(row)
    data["samples"] = json.loads(row["samples_json"])
    return jsonify(data)


@app.route("/api/laps/<int:lap_id>", methods=["DELETE"])
@require_api_key
def delete_lap(lap_id: int):
    db = get_db()
    db.execute("DELETE FROM laps WHERE id = ?", (lap_id,))
    db.commit()
    return "", 204


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
