from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from urllib.parse import urlparse

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage


CAPTIVE_MARKERS = (
    "eportal",
    "dr.com",
    "srun",
    "portal",
    "wlan_user_ip",
    "user_account",
    "login_method",
)


def _as_urls(check_urls: str | Sequence[str]) -> list[str]:
    if isinstance(check_urls, str):
        items = [item.strip() for item in check_urls.replace("\r", "\n").split("\n")]
    else:
        items = [str(item).strip() for item in check_urls]
    return [item for item in items if item]


def _host(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except ValueError:
        return ""


def _looks_like_captive_portal(response: requests.Response, detection: DetectionResult) -> bool:
    gateway_host = _host(detection.gateway)
    final_host = _host(response.url)
    if gateway_host and final_host and gateway_host == final_host:
        return True

    text = (response.text or "")[:5000].lower()
    if any(marker in text for marker in CAPTIVE_MARKERS):
        return True
    return False


class PortalAdapter(ABC):
    adapter_id: str
    name: str

    @abstractmethod
    def detect(self, page: PortalPage) -> DetectionResult:
        raise NotImplementedError

    @abstractmethod
    def login(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 15,
    ) -> LoginResult:
        raise NotImplementedError

    @abstractmethod
    def logout(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 10,
    ) -> LoginResult:
        raise NotImplementedError

    def check_status(
        self,
        session: requests.Session,
        detection: DetectionResult,
        check_url: str | Sequence[str],
        timeout: int = 5,
    ) -> bool:
        urls = _as_urls(check_url)
        if not urls:
            return False

        failures = 0
        for url in urls:
            try:
                response = session.get(url, timeout=timeout, allow_redirects=True)
            except requests.RequestException:
                failures += 1
                continue

            if _looks_like_captive_portal(response, detection):
                return False
            if response.status_code < 500:
                return True
            failures += 1

        return failures < len(urls)
