from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .utils import redact_sensitive


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_sensitive(original)


def get_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("campus_auto_login")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        log_dir / "campus_auto_login.log",
        maxBytes=512 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        RedactingFormatter("[%(asctime)s] %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    return logger
