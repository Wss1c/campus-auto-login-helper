from __future__ import annotations

from urllib.parse import urljoin

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage
from ..utils import compact_text, format_operator_account, origin
from .base import PortalAdapter


class SrunAdapter(PortalAdapter):
    adapter_id = "srun"
    name = "Srun / 深澜"

    def detect(self, page: PortalPage) -> DetectionResult:
        blob = (page.final_url + "\n" + page.text).lower()
        score = 0
        reasons: list[str] = []
        markers = [
            ("srun", 30, "包含 Srun 特征"),
            ("cgi-bin/srun_portal", 35, "发现 srun_portal 接口"),
            ("ac_id", 10, "发现 ac_id 参数"),
            ("n=200", 10, "发现 n=200 参数"),
            ("get_challenge", 20, "发现 challenge 接口"),
            ("srun_bx1", 20, "发现 Srun 加密函数"),
        ]
        for marker, points, reason in markers:
            if marker in blob:
                score += points
                reasons.append(reason)
        gateway = origin(page.final_url)
        login_endpoint = urljoin(gateway + "/", "cgi-bin/srun_portal")
        logout_endpoint = login_endpoint
        return DetectionResult(
            supported=score >= 70,
            adapter_id=self.adapter_id,
            adapter_name=self.name,
            score=min(score, 100),
            gateway=gateway,
            login_endpoint=login_endpoint,
            logout_endpoint=logout_endpoint,
            reason="；".join(reasons) or "未发现深澜关键特征",
            fields={"note": "第一版支持常见明文接口；强加密站点需后续模板扩展"},
        )

    def login(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 15,
    ) -> LoginResult:
        username = format_operator_account(
            credentials.username, credentials.operator_suffix
        )
        params = {
            "action": "login",
            "username": username,
            "password": credentials.password,
            "ac_id": detection.fields.get("ac_id", "1"),
            "type": "1",
            "n": "200",
        }
        try:
            response = session.get(detection.login_endpoint, params=params, timeout=timeout)
        except requests.RequestException as exc:
            return LoginResult(False, f"登录请求失败: {exc}", next_retry_seconds=60)
        text = response.text or ""
        success = response.status_code == 200 and (
            "login_ok" in text.lower()
            or '"ecode":0' in text.lower()
            or "online_ip" in text.lower()
        )
        return LoginResult(
            success,
            "登录成功" if success else "登录失败：该深澜站点可能启用了 challenge 加密",
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
        try:
            response = session.get(
                detection.logout_endpoint,
                params={"action": "logout", "username": credentials.username},
                timeout=timeout,
            )
        except requests.RequestException as exc:
            return LoginResult(False, f"注销请求失败: {exc}", next_retry_seconds=60)
        return LoginResult(
            response.status_code == 200,
            "注销请求已发送" if response.status_code == 200 else "注销失败",
            response.status_code,
            compact_text(response.text),
        )
