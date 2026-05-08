from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
)


def normalize_url(raw_url: str) -> str:
    value = (raw_url or "").strip()
    if not value:
        raise ValueError("请输入校园网登录页网址")
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", value):
        value = "http://" + value
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("网址格式不正确")
    path = parsed.path or "/"
    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


def origin(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def with_port(url: str, port: int) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or parsed.netloc
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{port}"
    return urlunparse((parsed.scheme or "http", netloc, "", "", "", ""))


def format_operator_account(username: str, operator_suffix: str) -> str:
    suffix = (operator_suffix or "").strip()
    if not suffix:
        return username.strip()
    suffix = suffix.lstrip("@")
    return f"{username.strip()}@{suffix}"


def compact_text(text: str, limit: int = 500) -> str:
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    return collapsed[:limit]


def redact_sensitive(text: str) -> str:
    value = text or ""
    patterns = [
        (r"(?i)(password|passwd|pwd|user_password|token|cookie|session|auth)(=|:)\s*[^&\s,;]+", r"\1\2 <redacted>"),
        (r"(?i)(user_password|password|passwd|pwd)=[^&\s]+", r"\1=<redacted>"),
        (r"(?i)(cookie:\s*)[^\r\n]+", r"\1<redacted>"),
        (r"(?i)(authorization:\s*)[^\r\n]+", r"\1<redacted>"),
    ]
    for pattern, replacement in patterns:
        value = re.sub(pattern, replacement, value)
    return value


class LoginPageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_chunks: list[str] = []
        self.in_title = False
        self.forms: list[dict[str, Any]] = []
        self.current_form: dict[str, Any] | None = None
        self.links: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k.lower(): v or "" for k, v in attrs}
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "form":
            self.current_form = {
                "method": (attr.get("method") or "get").lower(),
                "action": urljoin(self.base_url, attr.get("action") or self.base_url),
                "inputs": [],
            }
            self.forms.append(self.current_form)
        elif tag in {"input", "select", "textarea"} and self.current_form is not None:
            self.current_form["inputs"].append(
                {
                    "tag": tag,
                    "type": (attr.get("type") or "").lower(),
                    "name": attr.get("name") or "",
                    "id": attr.get("id") or "",
                    "value": attr.get("value") or "",
                }
            )
        elif tag == "a" and attr.get("href"):
            self.links.append(urljoin(self.base_url, attr["href"]))
        elif tag == "script" and attr.get("src"):
            self.scripts.append(urljoin(self.base_url, attr["src"]))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "form":
            self.current_form = None

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_chunks.append(data)

    @property
    def title(self) -> str:
        return compact_text(" ".join(self.title_chunks), 120)


def parse_login_page(html: str, base_url: str) -> LoginPageParser:
    parser = LoginPageParser(base_url)
    try:
        parser.feed(html or "")
    except Exception:
        pass
    return parser
