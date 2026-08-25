"""Tests for database session handling in backend.database."""

from httpx import ASGITransport, AsyncClient
import pytest

from backend import database as db_module
from backend.main import app as main_app

SENTINEL_PASSWORD = "SentinelPasswordMustNotBeLogged123!"  # pragma: allowlist secret


@pytest.fixture
async def client():
    """Async test client for the main app."""
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestValidationErrorsAreNotLogged:
    """A malformed request body must never be written to the error log.

    RequestValidationError is not an HTTPException, so it used to fall through
    to the catch-all handler in get_db() and be logged with a full traceback.
    That traceback embeds the raw request body, which on the auth routes
    includes the plaintext password the client submitted.
    """

    async def test_validation_error_is_not_logged(self, client, monkeypatch):
        """A 422 from body validation must not call logger.exception."""
        logged = []
        monkeypatch.setattr(
            db_module.logger,
            "exception",
            lambda *args, **kwargs: logged.append((args, kwargs)),
        )

        resp = await client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": SENTINEL_PASSWORD},
        )

        assert resp.status_code == 422
        assert logged == [], f"validation error was logged: {logged}"

    async def test_validation_error_response_is_still_returned(self, client):
        """Suppressing the log must not change what the client receives."""
        resp = await client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": SENTINEL_PASSWORD},
        )
        assert resp.status_code == 422
        assert "detail" in resp.json()
