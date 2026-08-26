import logging
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict
from pytest import LogCaptureFixture

from app.core.config import Settings
from app.main import create_app


def make_app() -> FastAPI:
    return create_app(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
        )
    )


async def test_every_response_has_generated_request_id() -> None:
    app = make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    UUID(response.headers["X-Request-ID"])


async def test_valid_incoming_request_id_is_preserved() -> None:
    app = make_app()
    request_id = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


async def test_invalid_incoming_request_id_is_replaced_with_uuid() -> None:
    app = make_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": "unsafe value"})

    assert response.headers["X-Request-ID"] != "unsafe value"
    UUID(response.headers["X-Request-ID"])


async def test_unknown_api_route_uses_unified_error_envelope() -> None:
    app = make_app()
    request_id = str(uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/does-not-exist", headers={"X-Request-ID": request_id})

    assert response.status_code == 404
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "code": "RESOURCE_NOT_FOUND",
        "message": "Ресурс не знайдено.",
        "field_errors": [],
        "request_id": request_id,
    }


async def test_validation_rejects_extra_fields_with_unified_field_errors() -> None:
    class StrictProbeRequest(BaseModel):
        model_config = ConfigDict(extra="forbid")

        email: str

    app = make_app()

    @app.post("/api/v1/_validation-probe")
    async def validation_probe(payload: StrictProbeRequest) -> dict[str, str]:
        return {"email": payload.email}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/_validation-probe", json={"unexpected": True})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["message"] == "Перевірте правильність заповнення полів."
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert response.json()["field_errors"] == [
        {"field": "email", "code": "missing", "message": "Поле є обов’язковим."},
        {
            "field": "unexpected",
            "code": "extra_forbidden",
            "message": "Невідоме поле.",
        },
    ]


async def test_internal_exception_is_safe_and_correlated(
    caplog: LogCaptureFixture,
) -> None:
    app = make_app()
    request_id = str(uuid4())
    secret_text = "postgresql+asyncpg://admin:secret@production/horeca"

    @app.get("/api/v1/_fault-probe")
    async def fault_probe() -> None:
        raise RuntimeError(secret_text)

    caplog.set_level(logging.ERROR)
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/_fault-probe", headers={"X-Request-ID": request_id})

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == request_id
    assert response.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Сталася внутрішня помилка. Спробуйте ще раз пізніше.",
        "field_errors": [],
        "request_id": request_id,
    }
    assert secret_text not in response.text
    assert secret_text not in caplog.text
    assert any(getattr(record, "request_id", None) == request_id for record in caplog.records)
