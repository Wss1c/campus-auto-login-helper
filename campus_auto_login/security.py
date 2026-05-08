from __future__ import annotations

import base64
import os
import sys


class CredentialProtector:
    """Protects passwords for the current Windows user.

    The preferred implementation is Windows DPAPI through pywin32. A weak
    base64 fallback is kept only so development tests can run on machines that
    do not expose DPAPI; production Windows builds should include pywin32.
    """

    PREFIX_DPAPI = "dpapi:"
    PREFIX_PLAIN_FALLBACK = "fallback:"

    def __init__(self, entropy: bytes = b"campus-auto-login") -> None:
        self.entropy = entropy

    def encrypt(self, value: str) -> str:
        data = (value or "").encode("utf-8")
        if sys.platform.startswith("win"):
            try:
                import win32crypt  # type: ignore

                encrypted = win32crypt.CryptProtectData(
                    data,
                    "CampusAutoLogin",
                    self.entropy,
                    None,
                    None,
                    0,
                )
                return self.PREFIX_DPAPI + base64.b64encode(encrypted).decode("ascii")
            except Exception:
                if os.environ.get("CAMPUS_AUTO_LOGIN_ALLOW_WEAK_CRYPTO") != "1":
                    raise
        return self.PREFIX_PLAIN_FALLBACK + base64.b64encode(data).decode("ascii")

    def decrypt(self, encrypted_value: str) -> str:
        if not encrypted_value:
            return ""
        if encrypted_value.startswith(self.PREFIX_DPAPI):
            payload = base64.b64decode(encrypted_value[len(self.PREFIX_DPAPI) :])
            import win32crypt  # type: ignore

            _, decrypted = win32crypt.CryptUnprotectData(
                payload,
                self.entropy,
                None,
                None,
                0,
            )
            return decrypted.decode("utf-8")
        if encrypted_value.startswith(self.PREFIX_PLAIN_FALLBACK):
            payload = encrypted_value[len(self.PREFIX_PLAIN_FALLBACK) :]
            return base64.b64decode(payload).decode("utf-8")
        raise ValueError("无法识别的密码存储格式，请重新输入密码")
