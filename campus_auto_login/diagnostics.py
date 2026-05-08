from __future__ import annotations

import json

from .models import DetectionResult, DiagnosticReport, PortalPage
from .utils import compact_text, parse_login_page, redact_sensitive


def build_diagnostic(
    page: PortalPage,
    detection: DetectionResult | None = None,
    error: str = "",
) -> DiagnosticReport:
    parser = parse_login_page(page.text, page.final_url)
    detected_adapter = detection.adapter_name if detection else ""
    score = detection.score if detection else 0
    return DiagnosticReport(
        requested_url=page.requested_url,
        final_url=page.final_url,
        status_code=page.status_code,
        title=parser.title,
        detected_adapter=detected_adapter,
        score=score,
        forms=parser.forms[:5],
        links=parser.links[:20],
        scripts=parser.scripts[:20],
        response_excerpt=redact_sensitive(compact_text(page.text, 1200)),
        error=error,
    )


def diagnostic_to_text(report: DiagnosticReport) -> str:
    payload = {
        "requested_url": report.requested_url,
        "final_url": report.final_url,
        "status_code": report.status_code,
        "title": report.title,
        "detected_adapter": report.detected_adapter,
        "score": report.score,
        "forms": report.forms,
        "links": report.links,
        "scripts": report.scripts,
        "response_excerpt": report.response_excerpt,
        "error": report.error,
    }
    return redact_sensitive(json.dumps(payload, ensure_ascii=False, indent=2))
