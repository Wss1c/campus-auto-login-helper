from __future__ import annotations

import datetime as _dt
import sys
import traceback
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def startup_log_path() -> Path:
    path = _base_dir() / "data" / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path / "startup_error.log"


def log_startup_event(message: str) -> None:
    line = f"[{_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n"
    startup_log_path().open("a", encoding="utf-8").write(line)


def log_startup_exception(exc: BaseException) -> Path:
    path = startup_log_path()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] startup failed\n")
        handle.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        handle.write("\n")
    return path


def show_native_error(title: str, message: str) -> None:
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, title, 0x00000010)
    except Exception:
        pass
