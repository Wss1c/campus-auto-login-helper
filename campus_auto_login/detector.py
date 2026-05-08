from __future__ import annotations

from dataclasses import dataclass

import requests

from .adapters import iter_adapters
from .diagnostics import build_diagnostic
from .models import DETECTION_THRESHOLD, DetectionResult, DiagnosticReport, PortalPage
from .utils import USER_AGENT, normalize_url


@dataclass(slots=True)
class DetectionOutcome:
    detected: DetectionResult | None
    candidates: list[DetectionResult]
    diagnostic: DiagnosticReport

    @property
    def supported(self) -> bool:
        return self.detected is not None and self.detected.is_confident


class DetectionEngine:
    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def fetch_page(self, raw_url: str) -> PortalPage:
        url = normalize_url(raw_url)
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        response = session.get(url, timeout=self.timeout, allow_redirects=True)
        response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        return PortalPage(
            requested_url=url,
            final_url=response.url,
            status_code=response.status_code,
            headers={k: v for k, v in response.headers.items()},
            text=response.text or "",
        )

    def detect(self, raw_url: str) -> DetectionOutcome:
        try:
            page = self.fetch_page(raw_url)
        except Exception as exc:
            url = raw_url.strip()
            page = PortalPage(url, url, 0, {}, "")
            diagnostic = build_diagnostic(page, None, f"无法访问该网址: {exc}")
            return DetectionOutcome(None, [], diagnostic)
        return self.detect_from_page(page)

    def detect_from_page(self, page: PortalPage) -> DetectionOutcome:
        candidates = [adapter.detect(page) for adapter in iter_adapters()]
        candidates.sort(key=lambda item: item.score, reverse=True)
        best = candidates[0] if candidates else None
        detected = best if best and best.supported and best.score >= DETECTION_THRESHOLD else None
        diagnostic = build_diagnostic(page, detected or best)
        return DetectionOutcome(detected, candidates, diagnostic)
