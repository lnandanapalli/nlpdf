"""FastAPI dependencies for authentication."""

from typing import NoReturn

from fastapi import Depends, HTTPException, Request, status
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.jwt import decode_access_token
from backend.crud.user_crud import get_user_by_email
from backend.database import get_db
from backend.models.user import User


def _reject(detail: str) -> NoReturn:
    """Raise HTTP 401 with the given detail message.

    Typed as NoReturn so that type-checkers narrow variables after the guard call.
    """
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the access_token cookie, then load and verify the user.

    Validates:
    1. Token signature and expiry (JWT decode)
    2. Token type is 'access'
    3. User exists in DB
    4. token_version matches — rejects tokens issued before logout/password-change (C3 fix)
    """
    token = request.cookies.get("access_token")
    if not token:
        _reject("Not authenticated")

    try:
        payload = decode_access_token(token)
        email: str | None = payload.get("sub")
        if email is None:
            _reject("Invalid token: missing subject")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from None
    except Exception:  # noqa: BLE001 — jwt.decode can raise undocumented exceptions
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from None

    user = await get_user_by_email(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # C3 fix: reject tokens issued before the last password change or logout-all.
    token_ver = payload.get("ver", 0)
    if token_ver != (user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked. Please log in again.",
        )

    return user


def get_current_session_id(request: Request) -> int | None:
    """Extract the session_id (sid) from the current access token without DB access.

    Returns None if the token is missing or malformed. Used by the sessions
    listing endpoint to mark which session is 'current'.
    """
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        sid = payload.get("sid")
        return int(sid) if sid is not None else None
    except Exception:  # noqa: BLE001 — any decoding error should return None gracefully
        return None
