"""Cookie helpers for setting and clearing auth cookies."""

import secrets

from fastapi import Response

from backend.config import settings


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set httpOnly access/refresh cookies and a non-httpOnly CSRF cookie."""
    secure = settings.COOKIE_SECURE
    domain = settings.COOKIE_DOMAIN

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=domain,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/auth/refresh",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        domain=domain,
    )

    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        domain=domain,
    )


def clear_auth_cookies(response: Response) -> None:
    """Delete all auth-related cookies."""
    domain = settings.COOKIE_DOMAIN

    response.delete_cookie(key="access_token", path="/", domain=domain)
    response.delete_cookie(key="refresh_token", path="/auth/refresh", domain=domain)
    response.delete_cookie(key="csrf_token", path="/", domain=domain)
