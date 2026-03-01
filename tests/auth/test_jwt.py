"""Tests for JWT token creation and verification."""

from datetime import datetime, timezone

import jwt as pyjwt
import pytest

from backend.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from backend.config import settings


class TestCreateAccessToken:
    """Tests for create_access_token."""

    def test_returns_string(self):
        token = create_access_token({"sub": "user@example.com"})
        assert isinstance(token, str)

    def test_token_contains_subject(self):
        token = create_access_token({"sub": "user@example.com"})
        payload = decode_access_token(token)
        assert payload["sub"] == "user@example.com"

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "test@test.com"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_token_has_access_type(self):
        token = create_access_token({"sub": "test@test.com"})
        payload = decode_access_token(token)
        assert payload["type"] == "access"


class TestCreateRefreshToken:
    """Tests for create_refresh_token."""

    def test_returns_string(self):
        token = create_refresh_token({"sub": "user@example.com"})
        assert isinstance(token, str)

    def test_token_has_refresh_type(self):
        token = create_refresh_token({"sub": "user@example.com"})
        payload = decode_refresh_token(token)
        assert payload["type"] == "refresh"

    def test_token_contains_subject(self):
        token = create_refresh_token({"sub": "user@example.com"})
        payload = decode_refresh_token(token)
        assert payload["sub"] == "user@example.com"

    def test_token_has_longer_expiry(self):
        access = create_access_token({"sub": "a@b.com"})
        refresh = create_refresh_token({"sub": "a@b.com"})

        access_payload = decode_access_token(access)
        refresh_payload = decode_refresh_token(refresh)

        assert refresh_payload["exp"] > access_payload["exp"]


class TestDecodeAccessToken:
    """Tests for decode_access_token."""

    def test_valid_token_succeeds(self):
        token = create_access_token({"sub": "a@b.com", "extra": 42})
        payload = decode_access_token(token)
        assert payload["sub"] == "a@b.com"
        assert payload["extra"] == 42

    def test_expired_token_raises(self):
        expired_payload = {
            "sub": "expired@test.com",
            "type": "access",
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
        }
        token = pyjwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_access_token(token)

    def test_invalid_token_raises(self):
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self):
        token = create_access_token({"sub": "user@test.com"})
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(tampered)

    def test_rejects_refresh_token(self):
        token = create_refresh_token({"sub": "user@test.com"})
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_access_token(token)


class TestDecodeRefreshToken:
    """Tests for decode_refresh_token."""

    def test_valid_token_succeeds(self):
        token = create_refresh_token({"sub": "a@b.com"})
        payload = decode_refresh_token(token)
        assert payload["sub"] == "a@b.com"

    def test_expired_token_raises(self):
        expired_payload = {
            "sub": "expired@test.com",
            "type": "refresh",
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
        }
        token = pyjwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(pyjwt.ExpiredSignatureError):
            decode_refresh_token(token)

    def test_rejects_access_token(self):
        token = create_access_token({"sub": "user@test.com"})
        with pytest.raises(pyjwt.InvalidTokenError):
            decode_refresh_token(token)
