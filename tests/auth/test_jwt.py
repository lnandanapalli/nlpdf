"""Tests for JWT token creation and verification."""

import jwt as pyjwt
import pytest

from backend.auth.jwt import create_access_token, decode_access_token


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


class TestDecodeAccessToken:
    """Tests for decode_access_token."""

    def test_valid_token_succeeds(self):
        token = create_access_token({"sub": "a@b.com", "extra": 42})
        payload = decode_access_token(token)
        assert payload["sub"] == "a@b.com"
        assert payload["extra"] == 42

    def test_expired_token_raises(self):
        # Create an already-expired token using PyJWT directly with the
        # real secret so decode_access_token can verify the signature.
        from datetime import datetime, timezone

        from backend.config import settings

        expired_payload = {
            "sub": "expired@test.com",
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
