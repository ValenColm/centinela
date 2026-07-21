"""Request-size limiting, rate limiting and operational request logging."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
import logging
import time
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("centinela.requests")


class PayloadTooLargeMiddleware:
    """Reject bodies over the configured size, even without Content-Length."""

    def __init__(self, app: Callable[..., Awaitable[None]], max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:  # type: ignore[no-untyped-def]
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length and int(content_length) > self.max_bytes:
            await JSONResponse({"detail": "Payload exceeds 100 KB"}, status_code=413)(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                await JSONResponse({"detail": "Payload exceeds 100 KB"}, status_code=413)(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        sent = False

        async def receive_body() -> dict[str, object]:
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, receive_body, send)


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, client_ip: str) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            requests = self._requests[client_ip]
            while requests and requests[0] <= now - self.window_seconds:
                requests.popleft()
            if len(requests) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - requests[0])))
                return False, retry_after
            requests.append(now)
            return True, 0


async def request_controls_and_logging(request: Request, call_next):  # type: ignore[no-untyped-def]
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = request.app.state.rate_limiter.allow(client_ip)
    started = time.perf_counter()
    if not allowed:
        response = JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        response.headers["Retry-After"] = str(retry_after)
    else:
        response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "request_completed ip=%s method=%s path=%s status=%s duration_ms=%s",
        client_ip,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response
