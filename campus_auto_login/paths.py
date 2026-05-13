from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_DATA_NAME = "CampusAutoLogin"
PORTABLE_FLAG_NAME = "portable.flag"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def portable_data_dir() -> Path:
    return app_dir() / "data"


def user_data_dir() -> Path:
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not root:
        return portable_data_dir()
    return Path(root) / APP_DATA_NAME


def portable_mode_enabled() -> bool:
    value = os.environ.get("CAMPUS_AUTO_LOGIN_PORTABLE", "").strip().lower()
    return value in {"1", "true", "yes"} or (app_dir() / PORTABLE_FLAG_NAME).exists()


def migrate_portable_data(target_dir: Path) -> None:
    source = portable_data_dir()
    if source == target_dir:
        return
    source_profiles = source / "profiles.json"
    target_profiles = target_dir / "profiles.json"
    if not source_profiles.exists() or target_profiles.exists():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target_dir, dirs_exist_ok=True)


def data_dir() -> Path:
    if portable_mode_enabled():
        path = portable_data_dir()
    else:
        path = user_data_dir()
        migrate_portable_data(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def logs_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
