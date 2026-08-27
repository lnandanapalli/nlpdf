"""Tests for request-error handling in backend.database."""

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
import pytest
from slowapi.errors import RateLimitExceeded

from backend.database import is_server_fault

SENTINEL_PASSWORD = "SentinelPasswordMustNotEscape123!"  # pragma: allowlist secret
LOGIN_BODY = {"email": "user@example.com", "password": SENTINEL_PASSWORD}


class TestCredentialsNeverEscape:
    """A rejected auth request must not leak the submitted password anywhere.

    Body validation fails before cf_token is checked, so the exception carries
    the whole request body. It used to reach two places: the log, via
    logger.exception() in get_db, and the 422 response body, via FastAPI's
    default handler serialising `input` verbatim.
    """

    async def test_password_never_reaches_the_log(self, client, captured_logs):
        resp = await client.post("/auth/login", json=LOGIN_BODY)

        assert resp.status_code == 422
        assert SENTINEL_PASSWORD not in captured_logs.getvalue()

    async def test_password_is_not_echoed_in_the_response(self, client):
        resp = await client.post("/auth/login", json=LOGIN_BODY)

        assert resp.status_code == 422
        assert SENTINEL_PASSWORD not in resp.text

    async def test_client_still_gets_actionable_errors(self, client):
        """Redaction must not strip what a client needs to fix the request."""
        resp = await client.post("/auth/login", json=LOGIN_BODY)

        detail = resp.json()["detail"]
        assert detail, "expected at least one validation error"
        for error in detail:
            assert {"type", "loc", "msg"} <= set(error)
            assert "input" not in error
            assert "ctx" not in error


class TestIsServerFault:
    """The logging rule is inverted: log unless positively known to be a client fault."""

    @pytest.mark.parametrize(
        "exc",
        [
            RequestValidationError([]),
            RateLimitExceeded.__new__(RateLimitExceeded),
            HTTPException(status_code=400, detail="bad request"),
            HTTPException(status_code=429, detail="slow down"),
        ],
    )
    def test_client_faults_are_not_logged(self, exc):
        assert is_server_fault(exc) is False

    @pytest.mark.parametrize(
        "exc",
        [
            HTTPException(status_code=500, detail="boom"),
            HTTPException(status_code=503, detail="unavailable"),
            RuntimeError("unexpected"),
            ValueError("unexpected"),
        ],
    )
    def test_server_faults_are_still_logged(self, exc):
        """Guards against an over-broad suppression silencing real failures."""
        assert is_server_fault(exc) is True
