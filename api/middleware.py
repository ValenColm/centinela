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

