"""Apex Trace API -- receives lap telemetry from the desktop app (wherever it
runs) and serves it back to the web dashboard (frontend/, behind Nginx).

Pure JSON API: the static dashboard itself is served by Nginx (see
frontend/), not by Flask -- mirrors the tennis site's split (Nginx serves the
SPA + proxies /api/* to this container, which is never exposed publicly on
its own).
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

DB_PATH = Path(os.environ.get("DATABASE_PATH", "/data/telemetry.db"))

app = Flask(__name__)


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

