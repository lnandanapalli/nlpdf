"""Tests for Cloudflare Turnstile verification."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.services.turnstile_service import verify_turnstile


def _mock_client(*, json_body=None, raise_for_status=None, post_error=None):
    """Build a stand-in for httpx.AsyncClient used as an async context manager."""
    response = MagicMock()
    response.json.return_value = json_body or {}
    if raise_for_status is not None:
        response.raise_for_status.side_effect = raise_for_status
    else:
        response.raise_for_status.return_value = None

    client = MagicMock()
    client.post = (
        AsyncMock(side_effect=post_error) if post_error else AsyncMock(return_value=response)
    )
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestVerifyTurnstile:
    """The CAPTCHA gate guards every unauthenticated auth route."""

    async def test_empty_token_is_rejected_without_a_network_call(self):
        with patch("backend.services.turnstile_service.httpx.AsyncClient") as factory:
            assert await verify_turnstile("") is False
            factory.assert_not_called()

    async def test_successful_verification(self):
        with patch(
            "backend.services.turnstile_service.httpx.AsyncClient",
            return_value=_mock_client(json_body={"success": True}),
        ):
            assert await verify_turnstile("good-token") is True

    async def test_rejected_token(self):
        with patch(
            "backend.services.turnstile_service.httpx.AsyncClient",
            return_value=_mock_client(
                json_body={"success": False, "error-codes": ["invalid-input-response"]}
            ),
        ):
            assert await verify_turnstile("bad-token") is False

    async def test_missing_success_key_is_treated_as_failure(self):
        """Fail closed if Cloudflare returns an unexpected shape."""
        with patch(
            "backend.services.turnstile_service.httpx.AsyncClient",
            return_value=_mock_client(json_body={}),
        ):
            assert await verify_turnstile("token") is False

    @pytest.mark.parametrize(
        "error",
        [
            httpx.RequestError("connection refused"),
            httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()),
        ],
    )
    async def test_network_failures_fail_closed(self, error):
        """An outage must not become an open door."""
        with patch(
            "backend.services.turnstile_service.httpx.AsyncClient",
            return_value=_mock_client(post_error=error),
        ):
            assert await verify_turnstile("token") is False

    async def test_non_2xx_response_fails_closed(self):
        with patch(
            "backend.services.turnstile_service.httpx.AsyncClient",
            return_value=_mock_client(
                raise_for_status=httpx.HTTPStatusError(
                    "403", request=MagicMock(), response=MagicMock()
                )
            ),
        ):
            assert await verify_turnstile("token") is False
