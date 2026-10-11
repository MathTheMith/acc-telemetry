"""Background recorder: no window, just a tray icon.

Meant to start with Windows (see install_autostart.bat) and wait for ACC:
as soon as the car is on track, every lap is saved and uploaded, without
having to think about launching anything. The mini overlay or the full
dashboard can still be opened on top of it for the live view; they leave
the recording to this process while it runs.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from PyQt5 import QtCore, QtGui, QtWidgets

from .lap_logger import LapLogger
from .uploader import DEFAULT_URL

DASHBOARD_URL = DEFAULT_URL.removesuffix("/api/laps")

FAST_POLL_MS = 33     # same sampling rate as the windows while driving
IDLE_POLL_MS = 10000  # ACC closed for a while: check every 10 s
# Pausing freezes the data too: keep polling fast for a while after the last
# sample, so resuming from a pause doesn't lose the first seconds of the lap.
STAY_FAST_S = 5 * 60
CONNECTION_TIMEOUT_S = 2.0


def _dot_icon(color: str) -> QtGui.QIcon:
    pix = QtGui.QPixmap(32, 32)
    pix.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pix)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setBrush(QtGui.QColor(color))
    painter.setPen(QtCore.Qt.NoPen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.end()
    return QtGui.QIcon(pix)


class BackgroundRecorder(QtCore.QObject):
    def __init__(self, reader, sessions_dir: str):
        super().__init__()
        self.reader = reader
        self.sessions_dir = sessions_dir
        self.logger = LapLogger(sessions_dir)
        self._last_sample_time = -STAY_FAST_S  # start in slow polling until ACC shows up
        self._state = None

        self._icon_idle = _dot_icon("#f0a020")
        self._icon_live = _dot_icon("#40d040")
        self.tray = None
        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QtWidgets.QSystemTrayIcon(self._icon_idle)
            menu = QtWidgets.QMenu()
            menu.addAction("Open dashboard", self._open_dashboard)
            menu.addAction("Open sessions folder", self._open_sessions_dir)
            menu.addSeparator()
            menu.addAction("Quit recorder", QtWidgets.QApplication.quit)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(self._on_tray_activated)
            self.tray.show()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(IDLE_POLL_MS)
        self._update_status()

    def _tick(self) -> None:
        now = time.monotonic()
        for _ in range(30):
            s = self.reader.poll()
            if s is None:
                break
            self._last_sample_time = now
            lap = self.logger.feed(s, now)
            if lap is not None:
                print(f"[recorder] lap {lap.number} saved ({self.logger.track}, {self.logger.car})")
        self._update_status()

    def _update_status(self) -> None:
        since_last = time.monotonic() - self._last_sample_time
        connected = since_last < CONNECTION_TIMEOUT_S
        interval = FAST_POLL_MS if since_last < STAY_FAST_S else IDLE_POLL_MS
        if interval != self._timer.interval():
            self._timer.setInterval(interval)
        state = (connected, self.logger.laps_saved)
        if state == self._state:
            return
        self._state = state
        if self.tray is not None:
            self.tray.setIcon(self._icon_live if connected else self._icon_idle)
            self.tray.setToolTip(
                f"ACC Telemetry recorder: {'recording' if connected else 'waiting for ACC'}\n"
                f"{self.logger.laps_saved} laps saved"
            )

    def _on_tray_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason) -> None:
        # Trigger = single left click on Windows; DoubleClick is included too
        # in case the platform only reports that one.
        if reason in (QtWidgets.QSystemTrayIcon.Trigger, QtWidgets.QSystemTrayIcon.DoubleClick):
            self._open_dashboard()

    def _open_dashboard(self) -> None:
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(DASHBOARD_URL))

    def _open_sessions_dir(self) -> None:
        path = Path(self.sessions_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        if hasattr(os, "startfile"):
            os.startfile(path)
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(path)))
