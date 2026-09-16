import json
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request, Response
from starlette.types import Message, Scope

from app.core.config import Settings
from app.main import create_app

BODY_LIMIT = 16 * 1024 * 1024


@pytest_asyncio.fixture
async def body_app() -> AsyncIterator[FastAPI]:
    app = create_app(
        Settings(
            _env_file=None,
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
            cors_allowed_origins=["https://frontend.test"],
        )
    )
    app.state.body_handler_calls = 0

    @app.post("/body-probe")
    async def probe(request: Request) -> Response:
        app.state.body_handler_calls += 1
        return Response(await request.body(), media_type="application/octet-stream")

    yield app
    await app.state.engine.dispose()


async def invoke(
    app: FastAPI,
    chunks: list[bytes],
    *,
    headers: list[tuple[bytes, bytes]] | None = None,
    disconnect: bool = False,
) -> tuple[list[Message], int]:
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/body-probe",
        "raw_path": b"/body-probe",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"origin", b"https://frontend.test"), *(headers or [])],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 443),
    }
    received = 0
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal received
        index = received
        received += 1
        if index >= len(chunks):
            assert disconnect, "The application read past the supplied request"
            return {"type": "http.disconnect"}
        return {
            "type": "http.request",
            "body": chunks[index],
            "more_body": disconnect or index < len(chunks) - 1,
        }

    async def send(message: Message) -> None:
        sent.append(message)

    await app(scope, receive, send)
    return sent, received


@pytest.mark.parametrize("length", [None, b"1", b"invalid"])
@pytest.mark.parametrize(
    "content_type",
    [
        b"application/json",
        b"application/problem+json",
        b"multipart/form-data",
        b"application/x-www-form-urlencoded",
        b"application/octet-stream",
    ],
)
async def test_stream_overflow_is_rejected_before_handler(
    body_app: FastAPI, length: bytes | None, content_type: bytes
) -> None:
    headers = [(b"content-type", content_type)]
    if length is not None:
        headers.append((b"content-length", length))
    sent, received = await invoke(body_app, [b"x" * BODY_LIMIT, b"x", b"unread"], headers=headers)
    assert sent[0]["status"] == 413
    assert body_app.state.body_handler_calls == 0
    assert received == 2
    response_headers = dict(sent[0]["headers"])
    assert response_headers[b"access-control-allow-origin"] == b"https://frontend.test"
    envelope = json.loads(sent[1]["body"])
    assert envelope["code"] == "REQUEST_BODY_TOO_LARGE"
    assert envelope["field_errors"] == []
    assert envelope["request_id"] == response_headers[b"x-request-id"].decode()


async def test_declared_overflow_is_rejected_without_reading(body_app: FastAPI) -> None:
    sent, received = await invoke(
        body_app, [], headers=[(b"content-length", str(BODY_LIMIT + 1).encode())]
    )
    assert sent[0]["status"] == 413
    assert received == body_app.state.body_handler_calls == 0


@pytest.mark.parametrize("size", [0, BODY_LIMIT - 1, BODY_LIMIT])
async def test_allowed_body_is_replayed_exactly(body_app: FastAPI, size: int) -> None:
    body = b"x" * size
    sent, received = await invoke(body_app, [body[: size // 2], body[size // 2 :]])
    assert sent[0]["status"] == 200
    assert sent[1]["body"] == body
    assert received == 2
    assert body_app.state.body_handler_calls == 1


async def test_disconnected_partial_request_does_not_reach_handler(body_app: FastAPI) -> None:
    sent, received = await invoke(body_app, [b"partial"], disconnect=True)
    assert sent == []
    assert received == 2
    assert body_app.state.body_handler_calls == 0


async def test_duplicate_length_cannot_hide_overflow(body_app: FastAPI) -> None:
    sent, received = await invoke(
        body_app,
        [],
        headers=[(b"content-length", b"1"), (b"content-length", str(BODY_LIMIT + 1).encode())],
    )
    assert sent[0]["status"] == 413
    assert received == body_app.state.body_handler_calls == 0


async def test_escaped_menu_sized_json_remains_usable(body_app: FastAPI) -> None:
    body = json.dumps({"text": "я" * (1024 * 1024 - 32)}, ensure_ascii=True).encode()
    assert 2 * 1024 * 1024 < len(body) < BODY_LIMIT
    sent, _ = await invoke(body_app, [body], headers=[(b"content-type", b"application/json")])
    assert sent[0]["status"] == 200
    assert sent[1]["body"] == body
