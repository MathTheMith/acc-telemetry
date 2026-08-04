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

    # ------------------------------------------------------------ ticking --
    def _tick(self) -> None:
        # Drain every sample available since the last tick (the reader may
        # produce data faster than the UI redraws) so no telemetry frame is
        # skipped, then redraw once using the most recent one.
        finished_laps = []
        got_any = False
        for _ in range(30):
            s = self.reader.poll()
            if s is None:
                break
            got_any = True
            self._last_sample = s
            finished = self._record_sample(s)
            if finished is not None:
                finished_laps.append(finished)

        if got_any:
            self._last_sample_time = time.monotonic()
            self._refresh_ui(self._last_sample)
            for lap in finished_laps:
                self._on_lap_finished(lap)

        connected = (time.monotonic() - self._last_sample_time) < CONNECTION_TIMEOUT_S
        if connected:
            self.status_label.setText("Connected to ACC")
            self.status_label.setStyleSheet("color: lightgreen; font-weight: bold;")
        else:
            self.status_label.setText("Waiting for ACC data...")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")

    def _record_sample(self, s: Sample) -> Optional[Lap]:
        finished = self.recorder.add_sample(s)
        self.hist_t.append(s.t)
        self.hist_gas.append(s.gas)
        self.hist_brake.append(s.brake)
        self.hist_speed.append(s.speed_kmh)
        return finished

    def _refresh_ui(self, s: Sample) -> None:
        self.track_label.setText(f"Track: {s.track}")
        self.car_label.setText(f"Car: {s.car_model}")
        self.session_store.update_meta(s.track, s.car_model)
        self.lap_count_label.setText(f"Lap: {s.completed_laps + 1}")
        self.current_time_label.setText(format_lap_time(s.current_time_ms))
        self.last_time_label.setText(f"Last lap: {format_lap_time(s.last_time_ms)}")
        self.best_time_label.setText(f"Best lap: {format_lap_time(s.best_time_ms)}")

        if s.last_time_ms > 0 and s.best_time_ms > 0:
            delta_ms = s.last_time_ms - s.best_time_ms
            if delta_ms <= 0:
                self.delta_label.setText("Last lap = best lap")
                self.delta_label.setStyleSheet("color: lightgreen;")
            else:
                self.delta_label.setText(f"+{delta_ms / 1000:.3f}s vs best")
                self.delta_label.setStyleSheet("color: salmon;")

        self._refresh_pedal_charts()

        if self.viewing_lap is None:
            self._refresh_live_map()

    def _refresh_pedal_charts(self) -> None:
        t = list(self.hist_t)
        self.curve_gas.setData(t, list(self.hist_gas))
        self.curve_brake.setData(t, list(self.hist_brake))
        self.curve_speed.setData(t, list(self.hist_speed))
        if t:
            self.plot_pedals.setXRange(t[-1] - WINDOW_SECONDS, t[-1], padding=0)

    def _refresh_live_map(self) -> None:
        lap = self.recorder.current_lap
        if not lap.x:
            return
        colors, sizes = lap_colors_and_sizes(lap.gas, lap.brake)
        brushes = [pg.mkBrush(int(r), int(g), int(b)) for r, g, b in colors]
        self.scatter_main.setData(x=lap.x, y=lap.z, brush=brushes, size=sizes, pen=None)
        self.marker_car.setData(x=[lap.x[-1]], y=[lap.z[-1]])

    def _on_lap_finished(self, lap: Lap) -> None:
        self.session_store.save_lap(lap)
        label = f"Lap {lap.number} - {format_lap_time(lap.lap_time_ms)}"
        if not lap.valid:
            label += " (invalid)"
        self.lap_list.addItem(label)
        self._refresh_best_ghost()

        track, car = self.session_store.track, self.session_store.car
        threading.Thread(
            target=self.uploader.upload, args=(lap, track, car), daemon=True
        ).start()

    def _refresh_best_ghost(self) -> None:
        best = self.recorder.best_lap
        if best is None or not best.x:
            self.scatter_best.clear()
            return
        colors, sizes = lap_colors_and_sizes(best.gas, best.brake)
        brushes = [pg.mkBrush(int(r), int(g), int(b), 110) for r, g, b in colors]
        self.scatter_best.setData(x=best.x, y=best.z, brush=brushes, size=sizes * 0.6, pen=None)

    # --------------------------------------------------------- lap review --
    def _on_lap_selected(self, item: QtWidgets.QListWidgetItem) -> None:
        row = self.lap_list.row(item)
        if row < 0 or row >= len(self.recorder.completed_laps):
            return
        lap = self.recorder.completed_laps[row]
        self.viewing_lap = lap
        self.live_button.setEnabled(True)
        self.marker_car.clear()

        colors, sizes = lap_colors_and_sizes(lap.gas, lap.brake)
        brushes = [pg.mkBrush(int(r), int(g), int(b)) for r, g, b in colors]
        self.scatter_main.setData(x=lap.x, y=lap.z, brush=brushes, size=sizes, pen=None)
        self.plot_map.setTitle(
            f"Lap {lap.number} - {format_lap_time(lap.lap_time_ms)} "
            f"(green=throttle, red=brake)"
        )

    def _show_live(self) -> None:
        self.viewing_lap = None
        self.live_button.setEnabled(False)
        self.plot_map.setTitle("Track map - green=throttle, red=brake")

    def closeEvent(self, event) -> None:
        self.reader.close()
        super().closeEvent(event)
