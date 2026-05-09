from __future__ import annotations

import logging
import threading
import time

import requests

from .adapters import get_adapter
from .models import Credentials, DetectionResult, LoginResult, Profile
from .power import AwakeGuard
from .utils import USER_AGENT


class AutoLoginService:
    def __init__(
        self,
        profile: Profile,
        password_provider,
        logger: logging.Logger,
        status_callback=None,
    ) -> None:
        self.profile = profile
        self.password_provider = password_provider
        self.logger = logger
        self.status_callback = status_callback
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._force_check = threading.Event()
        self._paused = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_login_ts = 0.0
        self._retry_after_ts = 0.0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._awake_guard = AwakeGuard()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        if self.profile.prevent_sleep_enabled:
            if self._awake_guard.enable():
                self._emit("已启用防睡眠，常驻期间电脑不会自动睡眠/休眠")
            else:
                self._emit("防睡眠启用失败，当前系统可能不支持")
        self._thread = threading.Thread(target=self._run, name="AutoLoginService", daemon=True)
        self._thread.start()
        self._emit("常驻已启动")

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._awake_guard.disable()
        self._emit("常驻已停止")

    def pause(self, paused: bool) -> None:
        if paused:
            self._paused.set()
            self._emit("已暂停自动登录")
        else:
            self._paused.clear()
            self._wake.set()
            self._emit("已恢复自动登录")

    def request_check(self, reason: str = "立即检查网络") -> None:
        self._emit(reason)
        self._force_check.set()
        self._wake.set()

    def update_profile(self, profile: Profile) -> None:
        self.profile = profile
        if profile.prevent_sleep_enabled and not self._awake_guard.enabled:
            if self._awake_guard.enable():
                self._emit("已启用防睡眠")
        elif not profile.prevent_sleep_enabled and self._awake_guard.enabled:
            self._awake_guard.disable()
            self._emit("已关闭防睡眠")

    def login_now(self) -> LoginResult:
        result = self._login()
        if result.success:
            self._last_login_ts = time.time()
            self._retry_after_ts = 0
        else:
            self._retry_after_ts = time.time() + max(result.next_retry_seconds, 60)
        return result

    def logout_now(self) -> LoginResult:
        adapter = get_adapter(self.profile.adapter_id)
        detection = self._detection()
        credentials = self._credentials()
        result = adapter.logout(self._session, detection, credentials)
        self._emit(result.message)
        self.logger.info("Logout: %s", result.message)
        return result

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._paused.is_set():
                    self._wait(5)
                    continue
                now = time.time()
                forced = self._force_check.is_set()
                self._force_check.clear()
                if forced:
                    if self._needs_login(now):
                        self.login_now()
                    else:
                        self._emit("网络检测正常，无需重新登录")
                elif now >= self._retry_after_ts and self._needs_login(now):
                    self.login_now()
                self._wait(max(5, self.profile.check_interval_seconds))
            except Exception as exc:
                self.logger.exception("Background auto-login loop failed")
                self._emit(f"常驻自动登录出错：{exc}")
                self._retry_after_ts = time.time() + 60
                self._wait(60)

    def _wait(self, seconds: int) -> None:
        self._wake.wait(seconds)
        self._wake.clear()

    def _needs_login(self, now: float) -> bool:
        adapter = get_adapter(self.profile.adapter_id)
        online = adapter.check_status(
            self._session,
            self._detection(),
            self.profile.check_urls or [self.profile.check_url],
        )
        if not self._last_login_ts:
            return not online
        if now - self._last_login_ts >= self.profile.login_interval_seconds:
            return True
        return not online

    def _login(self) -> LoginResult:
        adapter = get_adapter(self.profile.adapter_id)
        result = adapter.login(self._session, self._detection(), self._credentials())
        self._emit(result.message)
        self.logger.info("Login: %s; summary=%s", result.message, result.raw_summary)
        return result

    def _credentials(self) -> Credentials:
        return Credentials(
            username=self.profile.username,
            password=self.password_provider(self.profile),
            operator_suffix=self.profile.operator_suffix,
        )

    def _detection(self) -> DetectionResult:
        return DetectionResult(
            supported=True,
            adapter_id=self.profile.adapter_id,
            adapter_name=self.profile.adapter_name,
            score=100,
            gateway=self.profile.gateway,
            login_endpoint=self.profile.login_endpoint,
            logout_endpoint=self.profile.logout_endpoint,
            reason="来自已保存配置",
        )

    def _emit(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)
