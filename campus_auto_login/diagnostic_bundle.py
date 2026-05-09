from __future__ import annotations

import json
import platform
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Profile
from .utils import redact_sensitive


def _mask_username(username: str) -> str:
    if len(username) <= 4:
        return "*" * len(username)
    return username[:2] + "*" * (len(username) - 4) + username[-2:]


def _safe_profile(profile: Profile) -> dict:
    data = profile.to_dict()
    data.pop("encrypted_password", None)
    data["username"] = _mask_username(profile.username)
    return data


def export_diagnostic_bundle(
    *,
    output_dir: Path,
    profiles: Iterable[Profile],
    log_dir: Path,
    ui_log: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"campus_auto_login_diagnostic_{stamp}.zip"

    summary = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app": "CampusAutoLogin",
        "platform": platform.platform(),
        "profiles": [_safe_profile(profile) for profile in profiles],
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "summary.json",
            redact_sensitive(json.dumps(summary, ensure_ascii=False, indent=2)),
        )
        if ui_log.strip():
            archive.writestr("ui_log.txt", redact_sensitive(ui_log))
        for log_file in sorted(log_dir.glob("*.log")):
            try:
                archive.writestr(
                    f"logs/{log_file.name}",
                    redact_sensitive(log_file.read_text(encoding="utf-8", errors="replace")),
                )
            except OSError:
                continue

    return path
