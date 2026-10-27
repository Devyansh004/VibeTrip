"""Structured logging utility with secret sanitization."""

import logging
import re
import sys

_SENSITIVE_PATTERNS = [
    re.compile(r"(key|token|secret|password|auth|authorization)=([^\s&]+)", re.IGNORECASE),
    re.compile(r'("(?:api_key|token|secret|password|anon_key|service_role_key)"\s*:\s*")[^"]+(")', re.IGNORECASE),
]


class SanitizingFormatter(logging.Formatter):
    """Log formatter that masks credentials and sensitive tokens."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        sanitized = original
        for pattern in _SENSITIVE_PATTERNS:
            sanitized = pattern.sub(r"\1=***REDACTED***", sanitized)
        return sanitized


def setup_logger(name: str = "vibetrip") -> logging.Logger:
    """Create and configure a sanitized logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = SanitizingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = setup_logger("vibetrip")
