from __future__ import annotations

import sys
from typing import Any


ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


def _kernel32() -> Any | None:
    if sys.platform != "win32":
        return None
    try:
        import ctypes
    except ImportError:
        return None
    return ctypes.windll.kernel32


class AwakeGuard:
    """Keeps Windows awake while the auto-login service is resident."""

    def __init__(self) -> None:
        self.enabled = False

    def enable(self) -> bool:
        kernel32 = _kernel32()
        if kernel32 is None:
            self.enabled = False
            return False
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        result = kernel32.SetThreadExecutionState(flags)
        self.enabled = bool(result)
        return self.enabled

    def disable(self) -> None:
        kernel32 = _kernel32()
        if kernel32 is not None and self.enabled:
            kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        self.enabled = False
