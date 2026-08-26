import logging
from contextvars import ContextVar, Token
from uuid import UUID, uuid4

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
logger = logging.getLogger("app.errors")


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
        response_started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except Exception:
            logger.error("Unhandled application exception", extra={"request_id": request_id})
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
            _request_id.reset(token)
