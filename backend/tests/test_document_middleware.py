from collections.abc import Awaitable, Callable
from typing import cast

from anyio import run
from pydantic import SecretStr
from starlette.types import Message, Receive, Scope, Send

from app.config import Settings
from app.main import create_app
from app.middleware.document_body_limit import DocumentBodyLimitMiddleware


def http_scope(
    *,
    path: str = "/api/v1/documents/extract",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Scope:
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "server": ("testserver", 80),
        "client": ("testclient", 50_000),
        "scheme": "http",
        "method": "POST",
        "root_path": "",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "state": {},
    }


def test_internal_authentication_runs_before_document_body_is_consumed() -> None:
    app = create_app(
        settings=Settings(
            internal_api_token=SecretStr("configured-internal-token-that-is-long-enough")
        )
    )
    receive_called = False
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"private document", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    run(app, http_scope(), receive, send)

    assert receive_called is False
    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 401


def test_body_limit_counts_actual_chunks_when_content_length_is_false() -> None:
    sent: list[Message] = []
    messages: list[Message] = [
        {"type": "http.request", "body": b"abc", "more_body": True},
        {"type": "http.request", "body": b"de", "more_body": False},
    ]

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        while True:
            message = await receive()
            if not message.get("more_body", False):
                break
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = DocumentBodyLimitMiddleware(
        cast(Callable[[Scope, Receive, Send], Awaitable[None]], downstream),
        path="/api/v1/documents/extract",
        max_body_bytes=4,
    )

    async def receive() -> Message:
        return messages.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    run(
        middleware,
        http_scope(headers=[(b"content-length", b"1")]),
        receive,
        send,
    )

    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 413


def test_content_length_precheck_is_no_store_and_does_not_consume_body() -> None:
    downstream_called = False
    receive_called = False
    sent: list[Message] = []

    async def downstream(scope: Scope, receive: Receive, send: Send) -> None:
        nonlocal downstream_called
        downstream_called = True

    middleware = DocumentBodyLimitMiddleware(
        cast(Callable[[Scope, Receive, Send], Awaitable[None]], downstream),
        path="/api/v1/documents/extract",
        max_body_bytes=4,
    )

    async def receive() -> Message:
        nonlocal receive_called
        receive_called = True
        return {"type": "http.request", "body": b"private", "more_body": False}

    async def send(message: Message) -> None:
        sent.append(message)

    run(
        middleware,
        http_scope(headers=[(b"content-length", b"5")]),
        receive,
        send,
    )

    assert downstream_called is False
    assert receive_called is False
    response_start = next(message for message in sent if message["type"] == "http.response.start")
    assert response_start["status"] == 413
    headers = dict(response_start["headers"])
    assert headers[b"cache-control"] == b"no-store"
