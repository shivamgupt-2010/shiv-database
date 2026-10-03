import json
import logging
import sys
from typing import Any, Dict


class SensitiveDataFilter(logging.Filter):
    """Filter out or mask sensitive keys in log payloads."""

    SENSITIVE_KEYS = {
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "raw_key",
        "jwt_secret_key",
        "supabase_service_role_key",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, dict):
            record.msg = self._sanitize(record.msg)
        return True

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize(value)
            else:
                sanitized[key] = value
        return sanitized


def setup_logging():
    """Configure structured logging for SHIV Database V1."""
    log_formatter = logging.Formatter(
        '{"timestamp":"%(asctime)s", "level":"%(levelname)s", "logger":"%(name)s", "message":%(message)s}'
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(log_formatter)
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [handler]

    # Silence verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = logging.getLogger("shiv.database")
