from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

# Запас для JSON-екранування канонічного імпорту меню розміром до 2 MiB.
MAX_REQUEST_BODY_BYTES = 16 * 1024 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    declared_length = int(value)
                except ValueError:
                    continue
                if declared_length > MAX_REQUEST_BODY_BYTES:
                    await self._reject(scope, receive, send)
                    return

        # До перевірки фактичних байтів не запускаємо парсер, залежності чи транзакції.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                await self._reject(scope, receive, send)
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if replayed:
                return await receive()
            replayed = True
            content = bytes(body)
            body.clear()
            return {"type": "http.request", "body": content, "more_body": False}

        await self.app(scope, replay, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = error_response(
            status_code=413,
            code="REQUEST_BODY_TOO_LARGE",
            message="Тіло запиту перевищує дозволений розмір.",
        )
        await response(scope, receive, send)
