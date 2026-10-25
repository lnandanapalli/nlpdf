"""Cross-cutting behaviour of the deployed app: headers, CORS, CSRF, timeouts, errors."""

import asyncio
from unittest.mock import patch

from fastapi import Request
import pytest
from slowapi.errors import RateLimitExceeded

from backend.main import app, rate_limit_handler
from tests.integration.conftest import ORIGIN, make_pdf, new_client, sign_up_and_verify


class TestSecurityHeaders:
    async def test_every_response_carries_them(self, anon):
        resp = await anon.get("/")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]

    async def test_error_responses_carry_them_too(self, anon):
        resp = await anon.get("/auth/me")
        assert resp.status_code == 401
        assert resp.headers["x-frame-options"] == "DENY"

    async def test_hsts_only_outside_development(self, anon):
        with patch("backend.main.settings.APP_ENV", "development"):
            assert "strict-transport-security" not in (await anon.get("/")).headers
        with patch("backend.main.settings.APP_ENV", "production"):
            hsts = (await anon.get("/")).headers["strict-transport-security"]
        assert "max-age=31536000" in hsts


class TestCors:
    async def test_allowed_origin_gets_credentialed_cors(self, anon):
        resp = await anon.get("/")
        assert resp.headers["access-control-allow-origin"] == ORIGIN
        assert resp.headers["access-control-allow-credentials"] == "true"

    async def test_unknown_origin_gets_no_cors(self):
        async with new_client() as client:
            resp = await client.get("/", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in resp.headers

    async def test_preflight_allows_the_csrf_header(self, anon):
        resp = await anon.options(
            "/documents",
            headers={
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "X-CSRF-Token",
            },
        )
        assert resp.status_code == 200
        assert "x-csrf-token" in resp.headers["access-control-allow-headers"].lower()

    async def test_csrf_rejection_is_readable_by_the_browser(self, user):
        """Regression: CORS sat inside the CSRF middleware, so its 403s had no
        CORS headers and the browser reported a network error instead."""
        del user.headers["X-CSRF-Token"]
        resp = await user.delete("/documents")
        assert resp.status_code == 403
        assert resp.headers["access-control-allow-origin"] == ORIGIN


class TestCsrf:
    async def test_mutation_without_token_is_refused(self, user):
        del user.headers["X-CSRF-Token"]
        assert (await user.delete("/documents")).status_code == 403

    async def test_token_from_another_session_is_refused(self, user, outbox):
        async with new_client() as other:
            await sign_up_and_verify(other, outbox, "other@example.com")
            user.headers["X-CSRF-Token"] = other.cookies["csrf_token"]
            user.cookies.set("csrf_token", other.cookies["csrf_token"])
        resp = await user.delete("/documents")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "CSRF token mismatch"

    async def test_cross_site_mutation_from_unknown_origin_is_refused(self, user):
        resp = await user.delete(
            "/documents",
            headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
        )
        assert resp.status_code == 403

    async def test_exempt_auth_routes_still_require_json(self, anon):
        resp = await anon.post(
            "/auth/login",
            content="email=a@b.co&password=x",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 403
        assert "application/json" in resp.json()["detail"]

    async def test_valid_token_passes(self, user):
        assert (await user.delete("/documents")).status_code == 200


class TestErrorShapes:
    async def test_validation_errors_never_echo_the_submitted_password(self, anon):
        submitted = "hunter2-secret"  # pragma: allowlist secret
        resp = await anon.post("/auth/login", json={"password": submitted})
        assert resp.status_code == 422
        assert submitted not in resp.text
        assert {e["loc"][-1] for e in resp.json()["detail"]} >= {"email", "cf_token"}

    async def test_rate_limit_handler_returns_a_plain_429(self):
        request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})
        exc = RateLimitExceeded.__new__(RateLimitExceeded)
        resp = await rate_limit_handler(request, exc)
        assert resp.status_code == 429
        assert b"Too many requests" in resp.body

    async def test_slow_requests_time_out_with_a_readable_504(self, user, llm):
        async def stall(*args, **kwargs):
            await asyncio.sleep(5)

        llm.process_message = stall
        with patch("backend.main.settings.REQUEST_TIMEOUT_SECONDS", 0.2):
            resp = await user.post(
                "/pdf/process",
                files=[("files", ("a.pdf", make_pdf(1), "application/pdf"))],
                data={"message": "compress"},
            )
        assert resp.status_code == 504
        assert resp.json()["detail"] == "Request timed out. Try a smaller file."
        assert resp.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
async def test_api_docs_are_served(anon, path):
    # Kept public deliberately; this pins the decision so a change is visible.
    assert (await anon.get(path)).status_code == 200


def test_every_route_is_known():
    """Adding a route should be a conscious change: update this list and the README."""
    # Read from the OpenAPI schema: included routers are not flattened into
    # app.routes in current FastAPI.
    routes = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert routes == {
        ("GET", "/"),
        ("GET", "/health"),
        ("POST", "/pdf/process"),
        ("POST", "/auth/signup"),
        ("POST", "/auth/verify_otp"),
        ("POST", "/auth/resend_otp"),
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("POST", "/auth/logout"),
        ("GET", "/auth/me"),
        ("PUT", "/auth/profile"),
        ("POST", "/auth/change-password"),
        ("GET", "/auth/sessions"),
        ("DELETE", "/auth/sessions/{session_id}"),
        ("POST", "/auth/sessions/logout-all"),
        ("POST", "/auth/delete-account/request"),
        ("POST", "/auth/delete-account/confirm"),
        ("POST", "/auth/forgot-password"),
        ("POST", "/auth/reset-password"),
        ("GET", "/documents"),
        ("DELETE", "/documents/{document_id}"),
        ("DELETE", "/documents"),
    }
