# app/security.py
from fastapi import Security, HTTPException, Response
from fastapi.security.api_key import APIKeyHeader, APIKey
from starlette.status import HTTP_403_FORBIDDEN
from starlette.middleware.base import BaseHTTPMiddleware
from secure import Secure
from config import settings

# Security Setup
API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=True)

# Configure Secure Headers with relaxed CSP for GraphiQL
# Note: The 'secure' library API might differ based on version.
# Using a more standard way to set CSP if the builder pattern fails.

secure_headers = Secure.with_default_headers()

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        await secure_headers.set_headers_async(response)
        
        # Manually set CSP to ensure compatibility and correct values
        csp_value = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "connect-src 'self' http://localhost:5123 ws://localhost:5123;"
        )
        response.headers['Content-Security-Policy'] = csp_value
        
        # Add specific security headers
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
        response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers["X-SERVER-STATUS"] = "OK"
        return response

async def get_api_key(api_key_header: str = Security(API_KEY_HEADER)) -> APIKey:
    if api_key_header == settings.x_api_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN, detail="Could not validate API KEY"
        )