import logging
from contextvars import ContextVar, Token
from time import perf_counter
from uuid import UUID, uuid4

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.observability import bind_observability_context

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("app.http")


def get_request_id() -> str:
    return _request_id.get() or str(uuid4())


def _resolve_request_id(scope: Scope) -> str:
    incoming = Headers(scope=scope).get(REQUEST_ID_HEADER)
    if incoming is not None:
        try:
            UUID(incoming)
        except (ValueError, AttributeError):
            pass
        else:
            return incoming
    return str(uuid4())


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(scope)
        token: Token[str | None] = _request_id.set(request_id)
        started_at = perf_counter()
        response_started = False
        response_status = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started, response_status
            if message["type"] == "http.response.start":
                response_started = True
                response_status = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            with bind_observability_context(request_id=request_id):
                await self.app(scope, receive, send_with_request_id)
        except Exception as exc:
            logger.error(
                "http.request.unhandled",
                extra={"request_id": request_id, "exception_type": type(exc).__name__},
            )
            if response_started:
                raise
            response = JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "Сталася внутрішня помилка. Спробуйте ще раз пізніше.",
                    "field_errors": [],
                    "request_id": request_id,
                },
            )
            await response(scope, receive, send_with_request_id)
        finally:
            logger.info(
                "http.request.completed",
                extra={
                    "request_id": request_id,
                    "http_method": scope.get("method", ""),
                    "http_path": scope.get("path", ""),
                    "http_status": response_status,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                },
            )
            _request_id.reset(token)
