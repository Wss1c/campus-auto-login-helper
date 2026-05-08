from __future__ import annotations

from urllib.parse import urljoin

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage
from ..utils import compact_text, format_operator_account, origin
from .base import PortalAdapter


class H3CAdapter(PortalAdapter):
    adapter_id = "h3c_inode"
    name = "H3C / iNode Web Portal"

    def detect(self, page: PortalPage) -> DetectionResult:
        blob = (page.final_url + "\n" + page.text).lower()
        score = 0
        reasons: list[str] = []
        markers = [
            ("h3c", 35, "包含 H3C 特征"),
            ("inode", 35, "包含 iNode 特征"),
            ("portal", 10, "包含 portal 特征"),
            ("online.do", 20, "发现 online.do"),
            ("loginldap", 20, "发现 loginLdap"),
            ("userurl", 10, "发现 userurl 字段"),
        ]
        for marker, points, reason in markers:
            if marker in blob:
                score += points
                reasons.append(reason)
        gateway = origin(page.final_url)
        login_endpoint = urljoin(gateway + "/", "portal/online.do")
        logout_endpoint = urljoin(gateway + "/", "portal/logout.do")
        return DetectionResult(
            supported=score >= 70,
            adapter_id=self.adapter_id,
            adapter_name=self.name,
            score=min(score, 100),
            gateway=gateway,
            login_endpoint=login_endpoint,
            logout_endpoint=logout_endpoint,
            reason="；".join(reasons) or "未发现 H3C/iNode 关键特征",
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
        data = {
            "userName": username,
            "password": credentials.password,
            "loginType": "0",
            "userurl": "",
        }
        try:
            response = session.post(detection.login_endpoint, data=data, timeout=timeout)
        except requests.RequestException as exc:
            return LoginResult(False, f"登录请求失败: {exc}", next_retry_seconds=60)
        text = response.text or ""
        success = response.status_code == 200 and (
            "success" in text.lower() or "认证成功" in text or "online" in text.lower()
        )
        return LoginResult(
            success,
            "登录成功" if success else "登录失败：H3C/iNode 字段可能需要专门适配",
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
            response = session.post(detection.logout_endpoint, timeout=timeout)
        except requests.RequestException as exc:
            return LoginResult(False, f"注销请求失败: {exc}", next_retry_seconds=60)
        return LoginResult(
            response.status_code == 200,
            "注销请求已发送" if response.status_code == 200 else "注销失败",
            response.status_code,
            compact_text(response.text),
        )
