"""Tells whether the background recorder is already running.

The recorder holds a TCP port on localhost for as long as it lives: the OS
releases it automatically if the process dies, so there is no stale lock
file to clean up. The other windows (full dashboard, mini overlay) check it
before saving a lap, so a lap is never recorded and uploaded twice.
"""
from __future__ import annotations

import socket
from typing import Optional

RECORDER_PORT = 47391


def acquire_recorder_lock(port: int = RECORDER_PORT) -> Optional[socket.socket]:
    """Returns the bound socket (keep a reference to it for the process
    lifetime), or None if another process already holds the lock."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows: refuse shared binds
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen(1)
    except OSError:
        sock.close()
        return None
    return sock


def recorder_running(port: int = RECORDER_PORT) -> bool:
    lock = acquire_recorder_lock(port)
    if lock is None:
        return True
    lock.close()
    return False
