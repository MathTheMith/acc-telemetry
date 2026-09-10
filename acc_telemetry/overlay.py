"""Small always-on-top throttle/brake trace, meant to sit on screen while
driving (borderless/windowed ACC only -- exclusive fullscreen bypasses the
desktop compositor, so no overlay can show on top of it).

Keeps the same background job as the full dashboard (record laps to disk,
push finished laps to the web server) but with a minimal UI: just the
scrolling green/red pedal curve, draggable, no window chrome.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

import pyqtgraph as pg
from PyQt5 import QtCore, QtGui, QtWidgets

from .lap_recorder import Lap, LapRecorder
from .session_store import SessionStore
from .uploader import LapUploader

WINDOW_SECONDS = 6
REFRESH_MS = 33
CONNECTION_TIMEOUT_S = 2.0


class OverlayWindow(QtWidgets.QWidget):
    def __init__(self, reader, session_store: SessionStore):
        super().__init__()
        self.reader = reader
        self.session_store = session_store
        self.recorder = LapRecorder()
        self.uploader = LapUploader()
        self._last_sample_time = 0.0
        self._drag_pos: Optional[QtCore.QPoint] = None

        self.hist_t = deque(maxlen=WINDOW_SECONDS * 90)
        self.hist_gas = deque(maxlen=WINDOW_SECONDS * 90)
        self.hist_brake = deque(maxlen=WINDOW_SECONDS * 90)

        self.setWindowTitle("ACC Telemetry - mini")
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setStyleSheet("background-color: black;")
        self.resize(320, 130)
        self._build_ui()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(REFRESH_MS)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        pg.setConfigOptions(antialias=True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.status_dot = QtWidgets.QLabel("●")
        self.status_dot.setStyleSheet("color: orange;")
        close_btn = QtWidgets.QPushButton("✕")
        close_btn.setFixedSize(16, 16)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: white; border: none; }"
            "QPushButton:hover { color: red; }"
        )
        close_btn.clicked.connect(self.close)

        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addWidget(self.status_dot)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        self.plot = pg.PlotWidget(background="k")
        self.plot.setYRange(0, 1, padding=0)
        self.plot.hideAxis("left")
        self.plot.hideAxis("bottom")
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.setMenuEnabled(False)
        gas_pen = pg.mkPen((60, 220, 60), width=3)
        gas_pen.setCapStyle(QtCore.Qt.RoundCap)
        brake_pen = pg.mkPen((230, 60, 60), width=3)
        brake_pen.setCapStyle(QtCore.Qt.RoundCap)
        self.curve_gas = self.plot.plot(pen=gas_pen)
        self.curve_brake = self.plot.plot(pen=brake_pen)
        layout.addWidget(self.plot)

        bottom_bar = QtWidgets.QHBoxLayout()
        bottom_bar.addStretch()
        bottom_bar.addWidget(QtWidgets.QSizeGrip(self))
        layout.addLayout(bottom_bar)

    # ------------------------------------------------------------ ticking --
    def _tick(self) -> None:
        finished_laps = []
        got_any = False
        for _ in range(30):
            s = self.reader.poll()
            if s is None:
                break
            got_any = True
            finished = self.recorder.add_sample(s)
            self.hist_t.append(s.t)
            self.hist_gas.append(s.gas)
            self.hist_brake.append(s.brake)
            if finished is not None:
                finished_laps.append(finished)
            self.session_store.update_meta(s.track, s.car_model)

        if got_any:
            self._last_sample_time = time.monotonic()
            t = list(self.hist_t)
            self.curve_gas.setData(t, list(self.hist_gas))
            self.curve_brake.setData(t, list(self.hist_brake))
            if t:
                self.plot.setXRange(t[-1] - WINDOW_SECONDS, t[-1], padding=0)
            for lap in finished_laps:
                self._on_lap_finished(lap)

        connected = (time.monotonic() - self._last_sample_time) < CONNECTION_TIMEOUT_S
        self.status_dot.setStyleSheet(f"color: {'lightgreen' if connected else 'orange'};")

    def _on_lap_finished(self, lap: Lap) -> None:
        self.session_store.save_lap(lap)
        track, car = self.session_store.track, self.session_store.car
        threading.Thread(
            target=self.uploader.upload, args=(lap, track, car), daemon=True
        ).start()

    # ------------------------------------------------------ drag to move --
    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent) -> None:
        self._drag_pos = None

    def closeEvent(self, event) -> None:
        self.reader.close()
        super().closeEvent(event)
