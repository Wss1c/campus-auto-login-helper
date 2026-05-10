from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage
from ..utils import compact_text, format_operator_account, origin, with_port
from .base import PortalAdapter


def _parse_jsonp(text: str) -> dict:
    match = re.search(r"^[^(]*\((.*)\)\s*;?\s*$", text.strip(), re.S)
    if not match:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_already_online(payload: dict, text: str) -> bool:
    ret_code = _as_text(payload.get("ret_code"))
    message = (_as_text(payload.get("msg")) + "\n" + text).lower()
    explicit_markers = ("已经在线", "已在线", "已经登录", "已登录", "already online")
    if any(marker in message for marker in explicit_markers):
        return True
    return ret_code == "2" and ("在线" in message or "online" in message)


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _request_error_message(exc: requests.RequestException) -> str:
    if isinstance(exc, requests.Timeout):
        return "登录请求超时：校园网网关没有及时响应，请确认已连接校园网"
    if isinstance(exc, requests.ConnectionError):
        return "登录请求失败：无法连接校园网网关，请检查网关地址或当前网络"
    return f"登录请求失败: {exc}"


def classify_drcom_failure(
    result_value: str,
    gateway_message: str,
    status_code: int,
    summary: str,
) -> str:
    blob = f"{gateway_message}\n{summary}".lower()
    if _contains_any(blob, ("密码", "password", "passwd", "pwd", "认证失败", "auth failed")):
        return "登录失败：密码可能不正确，请重新输入密码后再试"
    if _contains_any(
        blob,
        ("运营商", "后缀", "service", "domain", "isp", "账号不存在", "用户不存在", "not exist", "unknown user"),
    ):
        return "登录失败：账号或运营商后缀可能不匹配"
    if _contains_any(blob, ("在线数", "终端", "设备", "最大连接", "limit", "too many", "max user")):
        return "登录失败：在线设备数量可能已达上限，请先注销其他终端"
    if _contains_any(blob, ("欠费", "余额", "停机", "限制", "冻结", "fee", "balance", "disabled")):
        return "登录失败：账号可能欠费、停机或被限制"

    if result_value == "2" or '"result":2' in summary:
        return "登录失败：账号可能不存在，或运营商后缀不匹配"
    if result_value == "3" or '"result":3' in summary:
        return "登录失败：账号可能欠费、停机或被限制"
    if result_value == "0" or '"result":0' in summary:
        if gateway_message:
            return f"登录失败：{gateway_message}"
        return "登录失败：网关拒绝登录请求，请检查账号、密码或运营商后缀"
    if status_code in {401, 403}:
        return f"登录失败：网关拒绝请求，HTTP {status_code}"
    if status_code >= 500:
        return f"登录失败：校园网网关异常，HTTP {status_code}"
    if not summary:
        return f"登录失败：网关返回空响应，HTTP {status_code}"
    return f"登录失败：HTTP {status_code}"


class DrComEportalAdapter(PortalAdapter):
    adapter_id = "drcom_eportal"
    name = "Dr.COM / ePortal"

    def detect(self, page: PortalPage) -> DetectionResult:
        blob = (page.final_url + "\n" + page.text).lower()
        score = 0
        reasons: list[str] = []

        checks = [
            ("eportal", 25, "包含 ePortal 特征"),
            ("/eportal/portal/login", 35, "发现登录接口路径"),
            ("dr1003", 20, "发现 Dr.COM JSONP callback"),
            ("login_method", 10, "发现 login_method 参数"),
            ("user_account", 10, "发现 user_account 参数"),
            ("wlan_user_ip", 10, "发现 wlan_user_ip 参数"),
            ("jsversion", 5, "发现 jsVersion 参数"),
            ("dr.comwebloginid", 45, "发现 Dr.COM WebLogin 页面标记"),
            ("a41.js", 20, "发现 Dr.COM WebLogin 脚本"),
            ("<title>注销页</title>", 20, "发现 Dr.COM 在线注销页"),
            ("oltime=", 10, "发现在线时长字段"),
            ("olflow=", 10, "发现在线流量字段"),
            ("uid=", 10, "发现在线用户字段"),
            ("v4ip=", 10, "发现客户端 IPv4 字段"),
            ("stime=", 5, "发现上线时间字段"),
            ("etime=", 5, "发现到期时间字段"),
        ]
        for marker, points, reason in checks:
            if marker in blob:
                score += points
                reasons.append(reason)

        login_match = re.search(
            r"https?://[^'\"\s<>]+/eportal/portal/login", page.text, re.I
        )
        logout_match = re.search(
            r"https?://[^'\"\s<>]+/eportal/portal/logout", page.text, re.I
        )

        parsed = urlparse(page.final_url)
        gateway = origin(page.final_url)
        if "/eportal/" not in parsed.path and parsed.port != 801:
            gateway = with_port(page.final_url, 801)

        login_endpoint = (
            login_match.group(0)
            if login_match
            else urljoin(gateway + "/", "eportal/portal/login")
        )
        logout_endpoint = (
            logout_match.group(0)
            if logout_match
            else urljoin(gateway + "/", "eportal/portal/logout")
        )

        score = min(score, 100)
        is_drcom_online_page = (
            "dr.comwebloginid" in blob
            and ("注销页" in page.text or "a41.js" in blob or "oltime=" in blob)
        )

        return DetectionResult(
            supported=score >= 70 or is_drcom_online_page,
            adapter_id=self.adapter_id,
            adapter_name=self.name,
            score=max(score, 85) if is_drcom_online_page else score,
            gateway=gateway,
            login_endpoint=login_endpoint,
            logout_endpoint=logout_endpoint,
            reason="；".join(reasons) or "未发现 ePortal 关键特征",
            fields={
                "account_format": ",0,{username}@operator",
                "page_kind": "online_logout" if is_drcom_online_page else "eportal",
            },
        )

    def _account(self, credentials: Credentials) -> str:
        account = format_operator_account(
            credentials.username, credentials.operator_suffix
        )
        return f",0,{account}"

    def login(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 15,
    ) -> LoginResult:
        params = {
            "callback": "dr1003",
            "login_method": "1",
            "user_account": self._account(credentials),
            "user_password": credentials.password,
            "wlan_user_ip": "",
            "wlan_user_ipv6": "",
            "wlan_user_mac": "000000000000",
            "wlan_ac_ip": "",
            "wlan_ac_name": "",
            "jsVersion": "4.2.1",
            "terminal_type": "1",
            "lang": "zh-cn",
            "v": "9961",
        }
        headers = {"Referer": detection.gateway + "/"}
        try:
            response = session.get(
                detection.login_endpoint,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            return LoginResult(False, _request_error_message(exc), next_retry_seconds=60)

        text = response.text or ""
        summary = compact_text(text)
        payload = _parse_jsonp(text)
        result_value = _as_text(payload.get("result")).lower()
        gateway_message = _as_text(payload.get("msg"))

        if response.status_code == 200 and (result_value in {"1", "true", "success"} or '"result":1' in text):
            return LoginResult(True, "登录成功", response.status_code, summary)
        if response.status_code == 200 and (result_value == "5" or '"result":5' in text):
            return LoginResult(True, "已在线，无需重复登录", response.status_code, summary)
        if response.status_code == 200 and _is_already_online(payload, text):
            return LoginResult(True, "已在线，无需重复登录", response.status_code, summary)

        message = classify_drcom_failure(result_value, gateway_message, response.status_code, summary)
        return LoginResult(False, message, response.status_code, summary, 60)

    def logout(
        self,
        session: requests.Session,
        detection: DetectionResult,
        credentials: Credentials,
        timeout: int = 10,
    ) -> LoginResult:
        params = {
            "callback": "dr1004",
            "login_method": "1",
            "user_account": self._account(credentials),
            "wlan_user_mac": "000000000000",
            "jsVersion": "4.2.1",
            "v": "6284",
        }
        try:
            response = session.get(
                detection.logout_endpoint,
                params=params,
                headers={"Referer": detection.gateway + "/"},
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
