from __future__ import annotations

import os
import sys
from pathlib import Path


STARTUP_NAME = "CampusAutoLogin.lnk"


def startup_folder() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("无法定位 Windows 启动文件夹")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def current_executable() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(sys.executable).resolve()


def set_startup(enabled: bool, minimized: bool = True) -> None:
    folder = startup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    shortcut = folder / STARTUP_NAME
    if not enabled:
        if shortcut.exists():
            shortcut.unlink()
        return

    exe = current_executable()
    args = "--minimized" if minimized and getattr(sys, "frozen", False) else "-m campus_auto_login --minimized"
    try:
        import win32com.client  # type: ignore

        shell = win32com.client.Dispatch("WScript.Shell")
        link = shell.CreateShortcut(str(shortcut))
        link.TargetPath = str(exe)
        link.Arguments = args
        link.WorkingDirectory = str(exe.parent)
        link.IconLocation = str(exe)
        link.Save()
    except Exception as exc:
        raise RuntimeError(f"创建开机自启快捷方式失败: {exc}") from exc


def is_startup_enabled() -> bool:
    return (startup_folder() / STARTUP_NAME).exists()
