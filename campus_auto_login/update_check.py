from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from . import __version__


LATEST_RELEASE_URL = "https://api.github.com/repos/Wss1c/campus-auto-login-helper/releases/latest"


@dataclass(slots=True)
class UpdateResult:
    ok: bool
    has_update: bool
    message: str
    url: str = ""


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", value)
    return tuple(int(part) for part in parts[:3]) or (0,)


def check_latest_release(timeout: int = 8) -> UpdateResult:
    try:
        response = requests.get(LATEST_RELEASE_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return UpdateResult(False, False, f"检查更新失败：{exc}")

    tag = str(payload.get("tag_name") or "")
    url = str(payload.get("html_url") or "")
    if not tag:
        return UpdateResult(False, False, "检查更新失败：未找到最新版本号")

    current = _version_tuple(__version__)
    latest = _version_tuple(tag)
    if latest > current:
        return UpdateResult(True, True, f"发现新版本 {tag}", url)
    return UpdateResult(True, False, f"当前已是最新版本 {__version__}", url)
