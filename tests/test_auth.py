import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.auth.csrf import verify_csrf_token
from backend.database import Base, get_db
from backend.routers.auth_router import router as auth_router
from backend.models.user import User
from sqlalchemy import select

# In-memory async SQLite for test isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_auth.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestSessionLocal = async_sessionmaker(
    bind=test_engine, class_=AsyncSession, expire_on_commit=False
)


def _create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    return app


app_instance = _create_test_app()


async def _override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app_instance.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def _mock_turnstile():
    """Bypass Cloudflare Turnstile verification in all auth tests."""
    with patch(
        "backend.routers.auth_router.verify_turnstile",
        new=AsyncMock(return_value=True),
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_email():
    """Replace the real Resend email call with a no-op."""
    with patch(
        "backend.routers.auth_router.send_otp_email",
        new=MagicMock(),
    ):
        yield


CF_TOKEN = "test-token"


@pytest.fixture(autouse=True)
async def _setup_db():
    """Create and tear down test tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture()
async def client():
    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _extract_cookies(response) -> dict[str, str]:
    """Extract Set-Cookie values from a response into a dict."""
    cookies = {}
    for header_val in response.headers.get_list("set-cookie"):
        name_value = header_val.split(";")[0]
        name, _, value = name_value.partition("=")
        cookies[name.strip()] = value.strip()
    return cookies


async def _create_verified_user_and_get_cookies(client, email, password):
    """Helper: signup, verify OTP, return cookies dict from verify_otp response."""
    # 1. Signup
    await client.post(
        "/auth/signup",
        json={"email": email, "password": password, "cf_token": CF_TOKEN},
    )

    # 2. Extract OTP from DB
    async with TestSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        assert user is not None, f"User {email} not found in DB"
        otp_code = user.otp_code

    # 3. Verify OTP
    resp = await client.post(
        "/auth/verify_otp", json={"email": email, "otp_code": otp_code}
    )
    assert resp.status_code == 200
    cookies = _extract_cookies(resp)
    return cookies


class TestSignup:
    """Tests for POST /auth/signup."""

    async def test_signup_returns_success(self, client):
        resp = await client.post(
            "/auth/signup",
            json={
                "email": "new@example.com",
                "password": "securepass123",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data
        assert "Verification code sent" in data["message"]

    async def test_signup_duplicate_email_returns_409_if_verified(self, client):
        payload = {"email": "dupe@example.com", "password": "securepass123"}
        await _create_verified_user_and_get_cookies(
            client, payload["email"], payload["password"]
        )

        resp2 = await client.post(
            "/auth/signup", json={**payload, "cf_token": CF_TOKEN}
        )
        assert resp2.status_code == 409

    async def test_signup_short_password_returns_422(self, client):
        resp = await client.post(
            "/auth/signup",
            json={
                "email": "short@example.com",
                "password": "short",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 422


class TestOTP:
    """Tests for POST /auth/verify_otp and /auth/resend_otp."""

    async def test_verify_otp_sets_cookies(self, client):
        email = "otp@example.com"
        await client.post(
            "/auth/signup",
            json={"email": email, "password": "securepass123", "cf_token": CF_TOKEN},
        )

        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            assert user is not None, f"User {email} not found in DB"
            otp_code = user.otp_code

        resp = await client.post(
            "/auth/verify_otp", json={"email": email, "otp_code": otp_code}
        )
        assert resp.status_code == 200
        cookies = _extract_cookies(resp)
        assert "access_token" in cookies
        assert "refresh_token" in cookies
        assert "csrf_token" in cookies
        # Body is a SuccessResponse, not TokenResponse
        data = resp.json()
        assert "message" in data
        assert "access_token" not in data

    async def test_verify_otp_invalid_code(self, client):
        email = "badotp@example.com"
        await client.post(
            "/auth/signup",
            json={"email": email, "password": "securepass123", "cf_token": CF_TOKEN},
        )

        resp = await client.post(
            "/auth/verify_otp", json={"email": email, "otp_code": "000000"}
        )
        assert resp.status_code == 401

    async def test_resend_otp_success(self, client):
        email = "resend@example.com"
        await client.post(
            "/auth/signup",
            json={"email": email, "password": "securepass123", "cf_token": CF_TOKEN},
        )

        resp = await client.post("/auth/resend_otp", json={"email": email})
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestLogin:
    """Tests for POST /auth/login."""

    async def test_login_sets_cookies(self, client):
        await _create_verified_user_and_get_cookies(
            client, "login@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/login",
            json={
                "email": "login@example.com",
                "password": "securepass123",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 200
        cookies = _extract_cookies(resp)
        assert "access_token" in cookies
        assert "refresh_token" in cookies
        assert "csrf_token" in cookies
        # Body is a SuccessResponse
        data = resp.json()
        assert "message" in data
        assert "access_token" not in data

    async def test_login_unverified_user_returns_403(self, client):
        await client.post(
            "/auth/signup",
            json={
                "email": "unverified@example.com",
                "password": "securepass123",
                "cf_token": CF_TOKEN,
            },
        )

        resp = await client.post(
            "/auth/login",
            json={
                "email": "unverified@example.com",
                "password": "securepass123",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 403
        assert "Unverified" in resp.json()["detail"]

    async def test_login_wrong_password_returns_401(self, client):
        await _create_verified_user_and_get_cookies(
            client, "wrong@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/login",
            json={
                "email": "wrong@example.com",
                "password": "badpassword",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 401


class TestMe:
    """Tests for GET /auth/me."""

    async def test_me_returns_user(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "me@example.com", "securepass123"
        )

        resp = await client.get(
            "/auth/me",
            cookies={"access_token": cookies["access_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert "id" in data

    async def test_me_without_cookie_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401


class TestRefresh:
    """Tests for POST /auth/refresh."""

    async def test_refresh_returns_new_cookies(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "refresh@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": cookies["refresh_token"]},
        )
        assert resp.status_code == 200
        new_cookies = _extract_cookies(resp)
        assert "access_token" in new_cookies
        assert "refresh_token" in new_cookies
        assert "csrf_token" in new_cookies
        # Body is a SuccessResponse
        data = resp.json()
        assert "message" in data

    async def test_refresh_without_cookie_returns_401(self, client):
        resp = await client.post("/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_with_access_token_returns_401(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "wrongtype@example.com", "securepass123"
        )

        # Use the access_token as if it were a refresh_token
        resp = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": cookies["access_token"]},
        )
        assert resp.status_code == 401

    async def test_refresh_with_expired_token_returns_401(self, client):
        import jwt as pyjwt
        from datetime import datetime, timezone

        from backend.config import settings

        expired_payload = {
            "sub": "expired@test.com",
            "type": "refresh",
            "exp": datetime(2020, 1, 1, tzinfo=timezone.utc),
        }
        expired_token = pyjwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        resp = await client.post(
            "/auth/refresh",
            cookies={"refresh_token": expired_token},
        )
        assert resp.status_code == 401


class TestLogout:
    """Tests for POST /auth/logout."""

    async def test_logout_clears_cookies_and_revokes_jti(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "logout@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/logout",
            cookies={"access_token": cookies["access_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Logged out successfully"

        # Verify cookies are cleared (set to empty / max-age=0)
        set_cookies = _extract_cookies(resp)
        for cookie_name in ("access_token", "refresh_token", "csrf_token"):
            # delete_cookie sets value to "" or a deletion marker
            if cookie_name in set_cookies:
                assert set_cookies[cookie_name] in ('""', "", "null")

        # Verify refresh token JTI is revoked in DB
        async with TestSessionLocal() as db:
            result = await db.execute(
                select(User).where(User.email == "logout@example.com")
            )
            user = result.scalars().first()
            assert user is not None
            assert user.refresh_token_jti is None

    async def test_logout_without_cookie_returns_401(self, client):
        resp = await client.post("/auth/logout")
        assert resp.status_code == 401


class TestCSRF:
    """Tests for CSRF middleware."""

    @pytest.fixture()
    async def csrf_client(self):
        """Client using an app with CSRF middleware enabled."""
        csrf_app = FastAPI()

        @csrf_app.middleware("http")
        async def csrf_mw(request: Request, call_next):
            error_response = verify_csrf_token(request)
            if error_response is not None:
                return error_response
            return await call_next(request)

        @csrf_app.post("/protected")
        async def protected():
            return {"ok": True}

        @csrf_app.get("/safe")
        async def safe():
            return {"ok": True}

        # Exempt path
        @csrf_app.post("/auth/login")
        async def login_exempt():
            return {"ok": True}

        transport = ASGITransport(app=csrf_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_get_request_passes_without_csrf(self, csrf_client):
        resp = await csrf_client.get("/safe")
        assert resp.status_code == 200

    async def test_exempt_path_passes_without_csrf(self, csrf_client):
        resp = await csrf_client.post("/auth/login")
        assert resp.status_code == 200

    async def test_missing_csrf_header_returns_403(self, csrf_client):
        resp = await csrf_client.post(
            "/protected",
            cookies={"csrf_token": "abc123"},
        )
        assert resp.status_code == 403
        assert "Missing CSRF token" in resp.json()["detail"]

    async def test_missing_csrf_cookie_returns_403(self, csrf_client):
        resp = await csrf_client.post(
            "/protected",
            headers={"X-CSRF-Token": "abc123"},
        )
        assert resp.status_code == 403
        assert "Missing CSRF token" in resp.json()["detail"]

    async def test_csrf_mismatch_returns_403(self, csrf_client):
        resp = await csrf_client.post(
            "/protected",
            cookies={"csrf_token": "correct_token"},
            headers={"X-CSRF-Token": "wrong_token"},
        )
        assert resp.status_code == 403
        assert "mismatch" in resp.json()["detail"]

    async def test_csrf_match_passes(self, csrf_client):
        token = "matching_csrf_token"
        resp = await csrf_client.post(
            "/protected",
            cookies={"csrf_token": token},
            headers={"X-CSRF-Token": token},
        )
        assert resp.status_code == 200
