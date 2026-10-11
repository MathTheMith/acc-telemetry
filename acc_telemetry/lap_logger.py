"""Records every lap without any UI: the core of the background recorder.

Unlike the windows, which live for one driving session, the recorder stays
up for days, so it opens a new session folder (and restarts lap numbering)
whenever the track or car changes, or after a long time without data (ACC
closed and relaunched later).
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from .lap_recorder import Lap, LapRecorder
from .sample import Sample
from .session_store import SessionStore
from .uploader import LapUploader

NEW_SESSION_AFTER_S = 10 * 60


def upload_in_background(uploader: LapUploader) -> Callable[[Lap, str, str], None]:
    def upload(lap: Lap, track: str, car: str) -> None:
        threading.Thread(target=uploader.upload, args=(lap, track, car), daemon=True).start()
    return upload


class LapLogger:
    def __init__(self, sessions_dir: str, upload: Optional[Callable[[Lap, str, str], None]] = None):
        self.sessions_dir = sessions_dir
        self.upload = upload if upload is not None else upload_in_background(LapUploader())
        self.recorder = LapRecorder()
        self.store: Optional[SessionStore] = None
        self.track = ""
        self.car = ""
        self.laps_saved = 0
        self._last_sample_at: Optional[float] = None

    def feed(self, s: Sample, now: float) -> Optional[Lap]:
        """`now` is a monotonic timestamp. Returns the lap it saved, if any."""
        # Replays and the pause menu also move the car: only real driving counts.
        if s.status != "ACC_LIVE" or not s.track:
            return None

        stale = self._last_sample_at is not None and now - self._last_sample_at > NEW_SESSION_AFTER_S
        if stale or (s.track, s.car_model) != (self.track, self.car):
            self._new_session(s.track, s.car_model)
        self._last_sample_at = now

        lap = self.recorder.add_sample(s)
        if lap is None:
            return None
        # Created on the first lap, so going on track and quitting at once
        # doesn't leave an empty session folder behind.
        if self.store is None:
            self.store = SessionStore(self.sessions_dir, track=self.track, car=self.car)
        self.store.save_lap(lap)
        self.laps_saved += 1
        self.upload(lap, self.track, self.car)
        return lap

    def _new_session(self, track: str, car: str) -> None:
        self.recorder = LapRecorder()
        self.store = None
        self.track = track
        self.car = car
