"""Live reader backed by ACC's shared memory.

Only works on Windows, with Assetto Corsa Competizione running, and requires
the `pyaccsharedmemory` package (Windows-only). Layout/field names follow the
community-documented ACC Shared Memory spec used by
https://github.com/rrennoir/PyAccSharedMemory
"""
from __future__ import annotations

import time
from typing import Optional

from .sample import Sample

try:
    from pyaccsharedmemory import accSharedMemory
    HAVE_ACC_SHARED_MEMORY = True
except ImportError:
    HAVE_ACC_SHARED_MEMORY = False


class AccReader:
    def __init__(self):
        if not HAVE_ACC_SHARED_MEMORY:
            raise RuntimeError(
                "pyaccsharedmemory is not available. This library only "
                "works on Windows (pip install pyaccsharedmemory)."
            )
        self._asm = accSharedMemory()
        self._t0 = time.monotonic()
