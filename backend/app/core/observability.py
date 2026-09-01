import json
import logging
import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, date, datetime
from enum import Enum
from typing import IO
from uuid import UUID

from app.core.config import Settings

REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
)
_STANDARD_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__)
_context: ContextVar[dict[str, object] | None] = ContextVar("observability_context", default=None)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def _safe_value(value: object, *, key: str | None = None) -> object:
    if key is not None and _is_sensitive_key(key):
        return REDACTED
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (UUID, date, datetime, Enum)):
        return str(value.value if isinstance(value, Enum) else value)
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_value(item, key=str(item_key)) for item_key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe_value(item) for item in value]
    return f"<{type(value).__name__}>"


@contextmanager
def bind_observability_context(**values: object | None) -> Iterator[None]:
    current = dict(_context.get() or {})
    current.update({key: value for key, value in values.items() if value is not None})
    token = _context.set(current)
    try:
        yield
    finally:
        _context.reset(token)


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, *, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
            "environment": self.environment,
        }
        payload.update(
            {key: _safe_value(value, key=key) for key, value in (_context.get() or {}).items()}
        )
        for key, value in record.__dict__.items():
            if key in _STANDARD_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = _safe_value(value, key=key)
        if record.exc_info is not None and record.exc_info[0] is not None:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_observability(settings: Settings, *, stream: IO[str] | None = None) -> logging.Logger:
    logger = logging.getLogger("app")
    logger.disabled = False
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.setFormatter(StructuredJsonFormatter(environment=settings.app_env))
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
    for name, candidate in logging.root.manager.loggerDict.items():
        if name.startswith("app.") and isinstance(candidate, logging.Logger):
            candidate.disabled = False
    return logger
