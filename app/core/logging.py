"""Structured logging (JSON in production, readable in development)."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter with standard fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, default=str)


class RequestIdFilter(logging.Filter):
    """Injects the current request id (from contextvars) into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        from app.middleware.request_context import current_request_id

        record.request_id = current_request_id.get()
        return True


def configure_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()
    root.setLevel(settings.LOG_LEVEL.upper())

    handler = logging.StreamHandler(sys.stdout)
    if settings.LOG_JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
        )
    handler.addFilter(RequestIdFilter())

    root.handlers.clear()
    root.addHandler(handler)

    # Keep dependency loggers quieter in JSON mode to avoid chatty output.
    for noisy in ("uvicorn.access", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the calling module."""
    return logging.getLogger(name)