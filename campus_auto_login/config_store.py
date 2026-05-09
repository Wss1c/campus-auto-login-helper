from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .models import Profile, default_check_urls, utc_now_iso
from .security import CredentialProtector


class ConfigStore:
    def __init__(self, data_dir: Path, protector: CredentialProtector | None = None) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "profiles.json"
        self.protector = protector or CredentialProtector()

    def load_profiles(self) -> list[Profile]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [Profile.from_dict(item) for item in data.get("profiles", [])]

    def save_profiles(self, profiles: list[Profile]) -> None:
        payload = {
            "version": 1,
            "profiles": [profile.to_dict() for profile in profiles],
        }
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upsert_profile(self, profile: Profile) -> None:
        profiles = self.load_profiles()
        profile.updated_at = utc_now_iso()
        for index, existing in enumerate(profiles):
            if existing.id == profile.id:
                profiles[index] = profile
                self.save_profiles(profiles)
                return
        profiles.append(profile)
        self.save_profiles(profiles)

    def delete_profile(self, profile_id: str) -> None:
        profiles = [p for p in self.load_profiles() if p.id != profile_id]
        self.save_profiles(profiles)

    def create_profile(
        self,
        *,
        name: str,
        login_url: str,
        adapter_id: str,
        adapter_name: str,
        gateway: str,
        login_endpoint: str,
        logout_endpoint: str,
        username: str,
        password: str,
        operator_label: str,
        operator_suffix: str,
        check_urls: list[str] | None = None,
    ) -> Profile:
        urls = check_urls or default_check_urls()
        return Profile(
            id=str(uuid.uuid4()),
            name=name,
            login_url=login_url,
            adapter_id=adapter_id,
            adapter_name=adapter_name,
            gateway=gateway,
            login_endpoint=login_endpoint,
            logout_endpoint=logout_endpoint,
            username=username,
            encrypted_password=self.protector.encrypt(password),
            operator_label=operator_label,
            operator_suffix=operator_suffix,
            check_urls=urls,
            check_url=urls[0],
        )

    def decrypt_password(self, profile: Profile) -> str:
        return self.protector.decrypt(profile.encrypted_password)

    def update_password(self, profile_id: str, password: str) -> Profile:
        profiles = self.load_profiles()
        for profile in profiles:
            if profile.id == profile_id:
                profile.encrypted_password = self.protector.encrypt(password)
                profile.updated_at = utc_now_iso()
                self.save_profiles(profiles)
                return profile
        raise KeyError(f"配置不存在: {profile_id}")

    def import_legacy_config(self, legacy_path: Path, adapter_defaults: dict[str, Any]) -> Profile | None:
        if not legacy_path.exists():
            return None
        data = json.loads(legacy_path.read_text(encoding="utf-8"))
        username = str(data.get("username") or "")
        password = str(data.get("password") or "")
        if not username or not password or username == "your_username":
            return None
        return self.create_profile(
            name="旧版校园网配置",
            login_url=str(adapter_defaults["login_url"]),
            adapter_id=str(adapter_defaults["adapter_id"]),
            adapter_name=str(adapter_defaults["adapter_name"]),
            gateway=str(adapter_defaults["gateway"]),
            login_endpoint=str(adapter_defaults["login_endpoint"]),
            logout_endpoint=str(adapter_defaults["logout_endpoint"]),
            username=username,
            password=password,
            operator_label="电信",
            operator_suffix="telecom",
        )
