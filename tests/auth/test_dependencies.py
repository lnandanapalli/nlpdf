"""get_current_user / get_current_session_id: every way a token can be wrong."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import jwt
import pytest

from backend.auth.dependencies import get_current_session_id, get_current_user
from backend.auth.jwt import create_access_token, create_refresh_token
from backend.config import settings
from backend.models.user import User

EMAIL = "dep@example.com"


def request_with(token: str | None) -> MagicMock:
    request = MagicMock()
    request.cookies = {} if token is None else {"access_token": token}
    return request


def user(token_version: int = 0) -> User:
    return User(
        id=7,
        email=EMAIL,
        hashed_password="x",  # pragma: allowlist secret
        token_version=token_version,
    )


async def resolve(token: str | None, found: User | None = None):
    with patch("backend.auth.dependencies.get_user_by_email", new=AsyncMock(return_value=found)):
        return await get_current_user(request_with(token), db=MagicMock())


async def expect_401(token: str | None, found: User | None = None) -> str:
    with pytest.raises(HTTPException) as exc_info:
        await resolve(token, found)
    assert exc_info.value.status_code == 401
    return exc_info.value.detail


async def test_valid_token_returns_the_user():
    token = create_access_token({"sub": EMAIL, "ver": 0, "sid": 1})
    assert (await resolve(token, user())).email == EMAIL


async def test_missing_cookie():
    assert await expect_401(None) == "Not authenticated"


async def test_expired_token():
    token = jwt.encode(
        {"sub": EMAIL, "type": "access", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    assert await expect_401(token, user()) == "Token has expired"


async def test_garbage_token():
    assert await expect_401("not.a.jwt", user()) == "Invalid token"


async def test_refresh_token_is_not_an_access_token():
    token, _ = create_refresh_token({"sub": EMAIL})
    assert await expect_401(token, user()) == "Invalid token"


async def test_token_without_subject():
    token = create_access_token({"ver": 0})
    await expect_401(token, user())


async def test_user_no_longer_exists():
    token = create_access_token({"sub": EMAIL, "ver": 0})
    assert await expect_401(token, None) == "User not found"


async def test_token_issued_before_logout_all_or_password_change():
    token = create_access_token({"sub": EMAIL, "ver": 0})
    detail = await expect_401(token, user(token_version=1))
    assert "revoked" in detail


async def test_token_without_version_claim_counts_as_version_zero():
    token = create_access_token({"sub": EMAIL})
    assert (await resolve(token, user(token_version=0))).id == 7


class TestGetCurrentSessionId:
    def test_reads_the_sid_claim(self):
        token = create_access_token({"sub": EMAIL, "sid": 42})
        assert get_current_session_id(request_with(token)) == 42

    @pytest.mark.parametrize("token", [None, "garbage"])
    def test_missing_or_bad_token_gives_none(self, token):
        assert get_current_session_id(request_with(token)) is None

    def test_token_without_sid_gives_none(self):
        assert get_current_session_id(request_with(create_access_token({"sub": EMAIL}))) is None
