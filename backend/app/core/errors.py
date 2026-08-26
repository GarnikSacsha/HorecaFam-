from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_id import get_request_id


class FieldError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field_errors: list[FieldError]
    request_id: str


def error_response(
    *, status_code: int, code: str, message: str, field_errors: list[FieldError] | None = None
) -> JSONResponse:
    envelope = ErrorEnvelope(
        code=code,
        message=message,
        field_errors=field_errors or [],
        request_id=get_request_id(),
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


def _field_path(location: tuple[int | str, ...]) -> str:
    transport_parts = {"body", "query", "path", "header", "cookie"}
    parts = [str(part) for part in location if str(part) not in transport_parts]
    return ".".join(parts) or "request"


def _field_message(error_code: str) -> str:
    messages = {
        "missing": "Поле є обов’язковим.",
        "extra_forbidden": "Невідоме поле.",
    }
    return messages.get(error_code, "Некоректне значення.")


async def http_exception_handler(
    _request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    if exception.status_code == 404:
        return error_response(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message="Ресурс не знайдено.",
        )
    return error_response(
        status_code=exception.status_code,
        code="HTTP_ERROR",
        message="Запит не може бути виконаний.",
    )


async def validation_exception_handler(
    _request: Request, exception: RequestValidationError
) -> JSONResponse:
    field_errors = [
        FieldError(
            field=_field_path(tuple(error["loc"])),
            code=str(error["type"]),
            message=_field_message(str(error["type"])),
        )
        for error in exception.errors()
    ]
    return error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Перевірте правильність заповнення полів.",
        field_errors=field_errors,
    )


def register_exception_handlers(application: FastAPI) -> None:
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    application.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
