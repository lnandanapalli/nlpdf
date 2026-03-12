"""CSRF protection: double-submit cookie pattern with HMAC session binding."""

import hmac

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.auth.cookies import make_csrf_token
from backend.config import settings

CSRF_EXEMPT_PATHS = {
    "/auth/signup",
    "/auth/login",
    "/auth/verify_otp",
    "/auth/resend_otp",
    "/auth/refresh",
}

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_csrf_token(request: Request) -> JSONResponse | None:
    """Verify the CSRF token is present, matches the header, AND is bound to the session.

    Two-layer validation:
      1. Double-submit: csrf_token cookie == X-CSRF-Token header
      2. Session binding: csrf_token == HMAC(secret, access_token)
         → Forged tokens (e.g. from subdomain cookie injection) are rejected
         → Tokens from other sessions / after logout are rejected

    Returns None if validation passes, or a 403 JSONResponse on failure.
    Skips validation for safe HTTP methods and CSRF-exempt paths.
    """
    # Ultimate CSRF Defense: Sec-Fetch Metadata (Modern Browsers)
    # If the browser explicitly tells us this request was initiated by a different website,
    # and it is a state-mutating request (POST/PUT/DELETE), we immediately block it.
    sec_fetch_site = request.headers.get("Sec-Fetch-Site")
    if sec_fetch_site == "cross-site" and request.method not in SAFE_METHODS:
        # Before blocking, check if it's originating from an explicitly trusted frontend domain
        req_origin = request.headers.get("origin", "")
        if req_origin not in settings.CORS_ALLOW_ORIGINS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-site requests strictly forbidden by Sec-Fetch metadata"},
            )
    if request.method in SAFE_METHODS:
        return None

    if request.url.path in CSRF_EXEMPT_PATHS:
        # Enforce that exempt POST requests must be API requests (not HTML form submissions).
        # Standard HTML forms cannot send application/json, so requiring it strictly
        # prevents Top-Level Navigation CSRF on these otherwise-exempt routes.
        if request.method not in SAFE_METHODS:
            content_type = request.headers.get("Content-Type", "")
            if "application/json" not in content_type:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Content-Type must be application/json (CSRF Protection)"},
                )
        return None

    return _verify_classic_csrf_tokens(request)


def _verify_classic_csrf_tokens(request: Request) -> JSONResponse | None:
    """Helper to validate the actual CSRF cookie to header bindings."""
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("X-CSRF-Token")
    access_token = request.cookies.get("access_token")

    # Both the cookie and the header must be present
    if not csrf_cookie or not csrf_header:
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing CSRF token"},
        )

    # Layer 1: classic double-submit — cookie must equal header
    if not hmac.compare_digest(csrf_cookie, csrf_header):
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token mismatch"},
        )

    # Layer 2: session binding — the token must be the HMAC of the current access token.
    # This ensures the token cannot be injected from another session or a subdomain.
    if not access_token:
        return JSONResponse(
            status_code=403,
            content={"detail": "Missing CSRF token"},
        )

    expected = make_csrf_token(access_token)
    if not hmac.compare_digest(csrf_cookie, expected):
        return JSONResponse(
            status_code=403,
            content={"detail": "CSRF token mismatch"},
        )

    return None
