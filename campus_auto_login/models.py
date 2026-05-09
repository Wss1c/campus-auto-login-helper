from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


DEFAULT_LOGIN_INTERVAL_SECONDS = 23 * 60 * 60
DEFAULT_CHECK_INTERVAL_SECONDS = 30
DEFAULT_CHECK_URL = "https://www.baidu.com"
DEFAULT_CHECK_URLS = [
    "https://www.baidu.com",
    "http://www.msftconnecttest.com/connecttest.txt",
    "http://connectivitycheck.gstatic.com/generate_204",
]
DETECTION_THRESHOLD = 70


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_check_urls() -> list[str]:
    return list(DEFAULT_CHECK_URLS)


def normalize_check_urls(value: Any) -> list[str]:
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("\r", "\n").split("\n")]
    elif isinstance(value, (list, tuple, set)):
        items = [str(item).strip() for item in value]
    else:
        items = []
    urls = [item for item in items if item]
    return urls or default_check_urls()


@dataclass(slots=True)
class PortalPage:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str]
    text: str


@dataclass(slots=True)
class DetectionResult:
    supported: bool
    adapter_id: str
    adapter_name: str
    score: int
    gateway: str
    login_endpoint: str = ""
    logout_endpoint: str = ""
    reason: str = ""
    fields: dict[str, Any] = field(default_factory=dict)

    @property
    def is_confident(self) -> bool:
        return self.supported and self.score >= DETECTION_THRESHOLD


@dataclass(slots=True)
class DiagnosticReport:
    requested_url: str
    final_url: str
    status_code: int
    title: str
    detected_adapter: str
    score: int
    forms: list[dict[str, Any]]
    links: list[str]
    scripts: list[str]
    response_excerpt: str
    error: str = ""


@dataclass(slots=True)
class Credentials:
    username: str
    password: str
    operator_suffix: str = ""


@dataclass(slots=True)
class LoginResult:
    success: bool
    message: str
    status_code: int = 0
    raw_summary: str = ""
    next_retry_seconds: int = 0


@dataclass(slots=True)
class Profile:
    id: str
    name: str
    login_url: str
    adapter_id: str
    adapter_name: str
    gateway: str
    login_endpoint: str
    logout_endpoint: str
    username: str
    encrypted_password: str
    operator_label: str = "campus"
    operator_suffix: str = ""
    check_url: str = DEFAULT_CHECK_URL
    check_urls: list[str] = field(default_factory=default_check_urls)
    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS
    login_interval_seconds: int = DEFAULT_LOGIN_INTERVAL_SECONDS
    resident_enabled: bool = False
    startup_enabled: bool = False
    prevent_sleep_enabled: bool = False
    resume_reconnect_enabled: bool = True
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "login_url": self.login_url,
            "adapter_id": self.adapter_id,
            "adapter_name": self.adapter_name,
            "gateway": self.gateway,
            "login_endpoint": self.login_endpoint,
            "logout_endpoint": self.logout_endpoint,
            "username": self.username,
            "encrypted_password": self.encrypted_password,
            "operator_label": self.operator_label,
            "operator_suffix": self.operator_suffix,
            "check_url": self.check_url,
            "check_urls": self.check_urls,
            "check_interval_seconds": self.check_interval_seconds,
            "login_interval_seconds": self.login_interval_seconds,
            "resident_enabled": self.resident_enabled,
            "startup_enabled": self.startup_enabled,
            "prevent_sleep_enabled": self.prevent_sleep_enabled,
            "resume_reconnect_enabled": self.resume_reconnect_enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        check_urls = normalize_check_urls(data.get("check_urls") or data.get("check_url"))
        check_url = str(data.get("check_url") or check_urls[0] or DEFAULT_CHECK_URL)
        return cls(
            id=str(data["id"]),
            name=str(data.get("name") or "校园网配置"),
            login_url=str(data["login_url"]),
            adapter_id=str(data["adapter_id"]),
            adapter_name=str(data.get("adapter_name") or data["adapter_id"]),
            gateway=str(data.get("gateway") or ""),
            login_endpoint=str(data.get("login_endpoint") or ""),
            logout_endpoint=str(data.get("logout_endpoint") or ""),
            username=str(data.get("username") or ""),
            encrypted_password=str(data.get("encrypted_password") or ""),
            operator_label=str(data.get("operator_label") or "campus"),
            operator_suffix=str(data.get("operator_suffix") or ""),
            check_url=check_url,
            check_urls=check_urls,
            check_interval_seconds=int(
                data.get("check_interval_seconds") or DEFAULT_CHECK_INTERVAL_SECONDS
            ),
            login_interval_seconds=int(
                data.get("login_interval_seconds") or DEFAULT_LOGIN_INTERVAL_SECONDS
            ),
            resident_enabled=bool(data.get("resident_enabled", False)),
            startup_enabled=bool(data.get("startup_enabled", False)),
            prevent_sleep_enabled=bool(data.get("prevent_sleep_enabled", False)),
            resume_reconnect_enabled=bool(data.get("resume_reconnect_enabled", True)),
            created_at=str(data.get("created_at") or utc_now_iso()),
            updated_at=str(data.get("updated_at") or utc_now_iso()),
        )
