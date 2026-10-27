"""Structured and sanitized logging for Sahaay."""

import logging
import re
import sys

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
    """Log formatter that automatically masks credentials and secrets."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        sanitized = original
        for pattern, replacement in SENSITIVE_PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure root logger with sanitized console output."""
    logger = logging.getLogger("sahaay")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    formatter = SanitizedFormatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.propagate = False
    return logger


logger = setup_logging()
