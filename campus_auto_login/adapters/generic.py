from __future__ import annotations

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage
from ..utils import compact_text, format_operator_account, parse_login_page
from .base import PortalAdapter


USERNAME_MARKERS = ("user", "username", "userid", "account", "login", "name")
PASSWORD_MARKERS = ("password", "passwd", "pwd", "pass")


def _field_matches(value: str, markers: tuple[str, ...]) -> bool:
    normalized = (value or "").lower()
    return any(marker in normalized for marker in markers)


class GenericFormAdapter(PortalAdapter):
    adapter_id = "generic_form"
    name = "通用表单登录"

    def detect(self, page: PortalPage) -> DetectionResult:
        parser = parse_login_page(page.text, page.final_url)
        best_form = None
        best_score = 0
        reason = "未找到明确的账号密码表单"
        for form in parser.forms:
            inputs = form.get("inputs", [])
            password_fields = [
                item
                for item in inputs
                if item.get("type") == "password"
                or _field_matches(item.get("name", ""), PASSWORD_MARKERS)
                or _field_matches(item.get("id", ""), PASSWORD_MARKERS)
            ]
            username_fields = [
                item
                for item in inputs
                if item.get("type") in {"text", "email", ""}
                and (
                    _field_matches(item.get("name", ""), USERNAME_MARKERS)
                    or _field_matches(item.get("id", ""), USERNAME_MARKERS)
                )
            ]
            if password_fields and username_fields:
                score = 70
                action = form.get("action") or page.final_url
                if "login" in action.lower() or "auth" in action.lower():
                    score += 15
                if (form.get("method") or "").lower() == "post":
                    score += 10
                if score > best_score:
                    best_score = score
                    best_form = form
                    reason = "发现明确的账号字段和密码字段"

        fields = {"form": best_form} if best_form else {}
        return DetectionResult(
            supported=best_score >= 70,
            adapter_id=self.adapter_id,
            adapter_name=self.name,
            score=min(best_score, 100),
            gateway=page.final_url,
            login_endpoint=(best_form or {}).get("action", "") if best_form else "",
            logout_endpoint="",
            reason=reason,
            fields=fields,
        )

    def login(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 15,
    ) -> LoginResult:
        form = detection.fields.get("form") or {}
        inputs = form.get("inputs") or []
        username = format_operator_account(
            credentials.username, credentials.operator_suffix
        )
        data: dict[str, str] = {}
        username_set = False
        password_set = False
        for item in inputs:
            name = item.get("name") or item.get("id")
            if not name:
                continue
            if not username_set and _field_matches(name, USERNAME_MARKERS):
                data[name] = username
                username_set = True
            elif not password_set and (
                item.get("type") == "password" or _field_matches(name, PASSWORD_MARKERS)
            ):
                data[name] = credentials.password
                password_set = True
            elif item.get("value"):
                data[name] = str(item.get("value"))
        if not username_set or not password_set:
            return LoginResult(False, "登录失败：无法确定通用表单字段", next_retry_seconds=60)

        method = (form.get("method") or "get").lower()
        url = detection.login_endpoint or detection.gateway
        try:
            if method == "post":
                response = session.post(url, data=data, timeout=timeout)
            else:
                response = session.get(url, params=data, timeout=timeout)
        except requests.RequestException as exc:
            return LoginResult(False, f"登录请求失败: {exc}", next_retry_seconds=60)
        text = response.text or ""
        failed = any(word in text.lower() for word in ["error", "failed", "invalid"])
        success = response.status_code < 400 and not failed
        return LoginResult(
            success,
            "登录请求已提交" if success else "登录失败：通用表单返回失败特征",
            response.status_code,
            compact_text(text),
            0 if success else 60,
        )

    def logout(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 10,
    ) -> LoginResult:
        return LoginResult(False, "通用表单模板暂不支持自动注销")
