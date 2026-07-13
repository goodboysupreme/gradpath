from typing import cast

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class _RequestBodyTooLarge(OSError):
    pass


class RequestBodyLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        path: str,
        max_body_bytes: int,
        detail: str,
    ) -> None:
        self._app = app
        self._path = path
        self._max_body_bytes = max_body_bytes
        self._detail = detail

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") != self._path:
            await self._app(scope, receive, send)
            return

        content_length = next(
            (value for key, value in scope.get("headers", []) if key.lower() == b"content-length"),
            None,
        )
        if content_length is not None:
            try:
                if int(content_length) > self._max_body_bytes:
                    await self._reject(scope, receive, send)
                    return
            except ValueError:
                pass

        received_bytes = 0
        response_started = False

        async def bounded_receive() -> Message:
            nonlocal received_bytes
            message = await receive()
            if message["type"] == "http.request":
                body = cast(bytes, message.get("body", b""))
                received_bytes += len(body)
                if received_bytes > self._max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def no_store_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = list(message.get("headers", []))
                headers = [item for item in headers if item[0].lower() != b"cache-control"]
                headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        try:
            await self._app(scope, bounded_receive, no_store_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, no_store_send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = JSONResponse(
            status_code=413,
            content={"detail": self._detail},
            headers={"Cache-Control": "no-store"},
        )
        await response(scope, receive, send)


class DocumentBodyLimitMiddleware(RequestBodyLimitMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        *,
        path: str,
        max_body_bytes: int,
    ) -> None:
        super().__init__(
            app,
            path=path,
            max_body_bytes=max_body_bytes,
            detail="Request body exceeds the document upload limit",
        )
