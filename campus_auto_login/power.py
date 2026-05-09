from __future__ import annotations

import ctypes
import sys


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class AwakeGuard:
    """Keeps Windows awake while the auto-login service is resident."""

    def __init__(self) -> None:
        self.enabled = False

    def enable(self) -> bool:
        if sys.platform != "win32":
            self.enabled = False
            return False
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        result = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        self.enabled = bool(result)
        return self.enabled

    def disable(self) -> None:
        if sys.platform == "win32" and self.enabled:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        self.enabled = False
