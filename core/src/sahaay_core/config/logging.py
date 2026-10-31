"""Structured and sanitized logging for Sahaay with persistent rotating log streams."""

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import sys
from typing import Optional

# Common patterns for sensitive information (tokens, keys, bearer tokens, passwords)
SENSITIVE_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}", re.IGNORECASE), r"\1[REDACTED_TOKEN]"),
    (
        re.compile(
            r"(['\"]?(?:api[_-]?key|token|secret|password|auth)['\"]?\s*[:=]\s*['\"])[^'\"]+(['\"])",
            re.IGNORECASE,
        ),
        r"\1[REDACTED]\2",
    ),
    (re.compile(r"(ghp_[A-Za-z0-9_]{36})"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(xox[baprs]-[A-Za-z0-9\-]+)"), "[REDACTED_SLACK_TOKEN]"),
    (re.compile(r"(AIza[0-9A-Za-z-_]{35})"), "[REDACTED_GOOGLE_KEY]"),
]


class SanitizedFormatter(logging.Formatter):
    """Log formatter that automatically masks credentials and secrets and supports correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        original = super().format(record)
        sanitized = original
        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized


def get_log_dir() -> Path:
    """Return canonical user local application data log directory (%LOCALAPPDATA%\\Sahaay\\logs)."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        p = Path(base) / "Sahaay" / "logs"
    else:
        p = Path.home() / "AppData" / "Local" / "Sahaay" / "logs"
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        # Fallback to local workspace logs if AppData is not writable
        p = Path("data") / "logs"
        p.mkdir(parents=True, exist_ok=True)
    return p


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger with sanitized console output and rotating file streams."""
    logger = logging.getLogger("sahaay")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    fmt = "%(asctime)s [%(levelname)s] [%(name)s] [%(correlation_id)s] %(message)s"
    formatter = SanitizedFormatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Attach persistent rotating file handlers
    try:
        log_dir = get_log_dir()
        backend_file = log_dir / "backend.log"
        file_handler = RotatingFileHandler(
            str(backend_file),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        pass

    logger.propagate = False
    return logger


logger = setup_logging()
