import json
import logging
from io import StringIO
from typing import cast
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import Settings
from app.core.observability import (
    StructuredJsonFormatter,
    bind_observability_context,
    configure_observability,
)
from app.core.request_id import RequestIDMiddleware


def _record_payload(formatter: logging.Formatter, **extra: object) -> dict[str, object]:
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="operation.completed",
        args=(),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    payload = json.loads(formatter.format(record))
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


def test_structured_formatter_redacts_nested_secrets_and_adds_context() -> None:
    formatter = StructuredJsonFormatter(environment="test")

    with bind_observability_context(
        request_id="8ba4e1b2-fb7d-4f25-89c6-1ae8306b5275",
        job_id="68022f6b-60a8-4389-9a22-908861ccddce",
        attempt_id="5a06973d-a6fb-4d47-a401-d64522f38af0",
    ):
        payload = _record_payload(
            formatter,
            details={
                "email": "safe@example.com",
                "password": "never-log-me",
                "nested": {"Authorization": "Bearer never-log-me"},
            },
        )

    assert payload["event"] == "operation.completed"
    assert payload["level"] == "info"
    assert payload["environment"] == "test"
    assert payload["request_id"] == "8ba4e1b2-fb7d-4f25-89c6-1ae8306b5275"
    assert payload["job_id"] == "68022f6b-60a8-4389-9a22-908861ccddce"
    assert payload["attempt_id"] == "5a06973d-a6fb-4d47-a401-d64522f38af0"
    assert payload["details"] == {
        "email": "safe@example.com",
        "password": "[REDACTED]",
        "nested": {"Authorization": "[REDACTED]"},
    }
    assert "never-log-me" not in json.dumps(payload)


def test_observability_configuration_uses_validated_level_and_one_json_handler() -> None:
    settings = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        log_level="WARNING",
    )
    stream = StringIO()

    logger = configure_observability(settings, stream=stream)
    logger.info("ignored")
    logger.warning("runtime.ready", extra={"component": "api"})

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) | {"timestamp": "ignored"} == {
        "timestamp": "ignored",
        "level": "warning",
        "logger": "app",
        "event": "runtime.ready",
        "environment": "test",
        "component": "api",
    }
    assert len(logger.handlers) == 1


@pytest.mark.asyncio
async def test_request_middleware_logs_safe_completion_with_response_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse({"ok": True})
        await response(scope, receive, send)

    app = RequestIDMiddleware(endpoint)
    app_logger = logging.getLogger("app")
    app_logger.handlers.clear()
    app_logger.propagate = True
    logging.getLogger("app.http").disabled = False
    caplog.set_level(logging.INFO, logger="app.http")

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://api.test",
    ) as client:
        response = await client.get(
            "/health?token=must-not-be-logged",
            headers={"X-Request-ID": "63fd85b7-1f45-4927-a5a3-e4dc2519f43e"},
        )

    record = next(record for record in caplog.records if record.msg == "http.request.completed")
    request_id = cast(str, record.__dict__["request_id"])
    assert request_id == response.headers["X-Request-ID"]
    assert UUID(request_id)
    assert record.__dict__["http_method"] == "GET"
    assert record.__dict__["http_path"] == "/health"
    assert record.__dict__["http_status"] == 200
    assert cast(float, record.__dict__["duration_ms"]) >= 0
    assert "must-not-be-logged" not in caplog.text
