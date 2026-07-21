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
import jwt
from fastapi import Request
from fastapi.responses import RedirectResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional

JWT_SECRET = "centinela-secret-key-12345"
JWT_ALGORITHM = "HS256"

def verify_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

def add_security_headers(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline';"
    )
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response

class AuthAndSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # Check if the path is public
        is_public = (
            path.startswith("/static") or 
            path == "/login" or 
            path == "/logout" or
            path == "/docs" or
            path == "/openapi.json"
        )
        
        user = None
        if not is_public:
            token = request.cookies.get("session_token")
            if not token:
                return add_security_headers(RedirectResponse(url="/login", status_code=303))
            
            user = verify_access_token(token)
            if not user:
                response = RedirectResponse(url="/login", status_code=303)
                response.delete_cookie("session_token")
                return add_security_headers(response)
            
            # Save user details in request state for route handlers
            request.state.user = user
            
            # Role authorization checks
            if path.startswith("/admin") and user.get("role") not in ["admin", "auditor"]:
                # Unauthorized to access admin pages
                html_content = """
                <html>
                    <head><title>403 Acceso Denegado</title><link rel="stylesheet" href="/static/styles.css"></head>
                    <body class="login-body">
                        <div class="login-card" style="text-align: center;">
                            <h2 class="text-danger" style="margin-bottom:1rem;">403 Acceso Denegado</h2>
                            <p style="margin-bottom:1.5rem; color:var(--text-secondary);">Tu rol actual no tiene permisos para acceder a esta sección.</p>
                            <a href="/casos" class="btn btn-primary">Volver al Panel</a>
                        </div>
                    </body>
                </html>
                """
                return add_security_headers(HTMLResponse(content=html_content, status_code=403))
                
            if path.startswith("/auditor") and user.get("role") != "auditor":
                # Unauthorized to access auditor pages
                html_content = """
                <html>
                    <head><title>403 Acceso Denegado</title><link rel="stylesheet" href="/static/styles.css"></head>
                    <body class="login-body">
                        <div class="login-card" style="text-align: center;">
                            <h2 class="text-danger" style="margin-bottom:1rem;">403 Acceso Denegado</h2>
                            <p style="margin-bottom:1.5rem; color:var(--text-secondary);">Esta sección es exclusiva para el rol de Auditor.</p>
                            <a href="/casos" class="btn btn-primary">Volver al Panel</a>
                        </div>
                    </body>
                </html>
                """
                return add_security_headers(HTMLResponse(content=html_content, status_code=403))

        response = await call_next(request)
        return add_security_headers(response)

