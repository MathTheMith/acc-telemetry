from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional

import pyqtgraph as pg
from PyQt5 import QtCore, QtWidgets

from .lap_recorder import Lap, LapRecorder
from .sample import Sample
from .session_store import SessionStore, format_lap_time
from .track_map import lap_colors_and_sizes
from .uploader import LapUploader

WINDOW_SECONDS = 15
REFRESH_MS = 33  # ~30 Hz UI refresh; polling itself can be faster than this
CONNECTION_TIMEOUT_S = 2.0


class TelemetryWindow(QtWidgets.QMainWindow):
    def __init__(self, reader, session_store: SessionStore):
        super().__init__()
        self.reader = reader
        self.session_store = session_store
        self.recorder = LapRecorder()
        self.uploader = LapUploader()
        self.viewing_lap: Optional[Lap] = None
        self._last_sample: Optional[Sample] = None
        self._last_sample_time = 0.0

        self.hist_t = deque(maxlen=WINDOW_SECONDS * 90)
        self.hist_gas = deque(maxlen=WINDOW_SECONDS * 90)
        self.hist_brake = deque(maxlen=WINDOW_SECONDS * 90)
        self.hist_speed = deque(maxlen=WINDOW_SECONDS * 90)

        self.setWindowTitle("ACC Telemetry - Trail Braking")
        self.resize(1400, 850)
        self._build_ui()

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(REFRESH_MS)

    # ---------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        pg.setConfigOptions(antialias=True, background="k", foreground="w")

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.setCentralWidget(splitter)

        # --- left: scrolling telemetry curves ---
        left = QtWidgets.QWidget()
        left_layout = QtWidgets.QVBoxLayout(left)

        self.plot_pedals = pg.PlotWidget()
        self.plot_pedals.setYRange(0, 1)
        self.plot_pedals.setLabel("left", "Pedal (0-1)")
        self.plot_pedals.setLabel("bottom", "Time (s)")
        self.plot_pedals.addLegend()
        self.curve_gas = self.plot_pedals.plot(
            pen=pg.mkPen((60, 220, 60), width=2), name="Throttle"
        )
        self.curve_brake = self.plot_pedals.plot(
            pen=pg.mkPen((230, 60, 60), width=2), name="Brake"
        )

        self.plot_speed = pg.PlotWidget()
        self.plot_speed.setLabel("left", "Speed (km/h)")
        self.plot_speed.setLabel("bottom", "Time (s)")
        self.plot_speed.setXLink(self.plot_pedals)
        self.curve_speed = self.plot_speed.plot(pen=pg.mkPen((80, 160, 255), width=2))

        left_layout.addWidget(self.plot_pedals, 2)
        left_layout.addWidget(self.plot_speed, 1)
        splitter.addWidget(left)

        # --- right: info + track map + lap list ---
        right = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right)

        self.status_label = QtWidgets.QLabel("Waiting for ACC data...")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")
        self.track_label = QtWidgets.QLabel("Track: -")
        self.car_label = QtWidgets.QLabel("Car: -")
        self.lap_count_label = QtWidgets.QLabel("Lap: -")

        self.current_time_label = QtWidgets.QLabel("--:--.---")
        self.current_time_label.setStyleSheet("font-size: 28px; font-weight: bold;")
        self.last_time_label = QtWidgets.QLabel("Last lap: --:--.---")
        self.best_time_label = QtWidgets.QLabel("Best lap: --:--.---")
        self.delta_label = QtWidgets.QLabel("")

        info_box = QtWidgets.QGroupBox("Session")
        info_layout = QtWidgets.QVBoxLayout(info_box)
        for w in (
            self.status_label,
            self.track_label,
            self.car_label,
            self.lap_count_label,
            self.current_time_label,
            self.last_time_label,
            self.best_time_label,
            self.delta_label,
        ):
            info_layout.addWidget(w)

        self.plot_map = pg.PlotWidget()
        self.plot_map.setAspectLocked(True)
        self.plot_map.setTitle("Track map - green=throttle, red=brake")
        self.scatter_best = pg.ScatterPlotItem(size=4)
        self.scatter_main = pg.ScatterPlotItem(size=7)
        self.marker_car = pg.ScatterPlotItem(
            size=14, brush=pg.mkBrush(255, 255, 0), pen=pg.mkPen("k")
        )
        self.plot_map.addItem(self.scatter_best)
        self.plot_map.addItem(self.scatter_main)
        self.plot_map.addItem(self.marker_car)

        self.lap_list = QtWidgets.QListWidget()
        self.lap_list.itemDoubleClicked.connect(self._on_lap_selected)
        self.live_button = QtWidgets.QPushButton("Back to live")
        self.live_button.clicked.connect(self._show_live)
        self.live_button.setEnabled(False)

        laps_box = QtWidgets.QGroupBox("Laps (double-click to compare)")
        laps_layout = QtWidgets.QVBoxLayout(laps_box)
        laps_layout.addWidget(self.lap_list)
        laps_layout.addWidget(self.live_button)

        right_layout.addWidget(info_box)
        right_layout.addWidget(self.plot_map, 2)
        right_layout.addWidget(laps_box, 1)
        splitter.addWidget(right)

        splitter.setSizes([850, 550])
