"""Entry point: launches the live ACC telemetry dashboard.

Usage:
    python main.py            # real ACC shared memory (Windows + ACC running)
    python main.py --sim      # simulator, no ACC/wheel needed (demo/test)
    python main.py --mini     # small always-on-top throttle/brake overlay
"""
from __future__ import annotations

import argparse
import sys

from PyQt5 import QtWidgets

from acc_telemetry.live_view import TelemetryWindow
from acc_telemetry.session_store import SessionStore


def build_reader(use_sim: bool):
    if use_sim:
        from acc_telemetry.simulator import SimulatedReader
        return SimulatedReader()

    from acc_telemetry.reader import AccReader, HAVE_ACC_SHARED_MEMORY
    if not HAVE_ACC_SHARED_MEMORY:
        print(
            "pyaccsharedmemory unavailable (Windows only).\n"
            "Re-run with --sim to test without ACC, or install the library on "
            "Windows: pip install pyaccsharedmemory"
        )
        sys.exit(1)
    return AccReader()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sim", action="store_true", help="use the simulator instead of ACC"
    )
    parser.add_argument(
        "--mini", action="store_true",
        help="small always-on-top throttle/brake overlay instead of the full dashboard",
    )
    parser.add_argument(
        "--sessions-dir", default="sessions", help="directory where laps are saved"
    )
    args = parser.parse_args()

    reader = build_reader(args.sim)
    session_store = SessionStore(args.sessions_dir, track="waiting", car="waiting")

    app = QtWidgets.QApplication(sys.argv)
    if args.mini:
        from acc_telemetry.overlay import OverlayWindow
        window = OverlayWindow(reader, session_store)
    else:
        window = TelemetryWindow(reader, session_store)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
