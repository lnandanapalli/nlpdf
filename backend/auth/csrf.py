"""CSRF protection using the double-submit cookie pattern."""

from fastapi import Request
from fastapi.responses import JSONResponse

CSRF_EXEMPT_PATHS = {
    "/auth/signup",
    "/auth/login",
    "/auth/verify_otp",
    "/auth/resend_otp",
    "/auth/refresh",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_csrf_token(request: Request) -> JSONResponse | None:
    """Compare the csrf_token cookie against the X-CSRF-Token header.

    Returns None if CSRF validation passes, or a 403 JSONResponse on failure.
    Skips validation for safe HTTP methods and exempt paths.
    """
    if request.method in SAFE_METHODS:
        return None

    if request.url.path in CSRF_EXEMPT_PATHS:
        return None

    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("X-CSRF-Token")

    if not cookie_token or not header_token:
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing CSRF token"},
        )

    if cookie_token != header_token:
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token mismatch"},
        )

    return None
