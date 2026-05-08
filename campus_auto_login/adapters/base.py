from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from ..models import Credentials, DetectionResult, LoginResult, PortalPage


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
        check_url: str,
        timeout: int = 5,
    ) -> bool:
        try:
            response = session.get(check_url, timeout=timeout)
            return response.status_code < 500
        except requests.RequestException:
            return False
