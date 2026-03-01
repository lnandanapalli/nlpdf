import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


async def _create_verified_user_and_get_tokens(client, email, password):
    """Helper: signup, verify OTP, return (access_token, refresh_token)."""
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
    data = resp.json()
    return data["access_token"], data["refresh_token"]


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
        await _create_verified_user_and_get_tokens(
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

    async def test_verify_otp_success(self, client):
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
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

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

    async def test_login_success(self, client):
        await _create_verified_user_and_get_tokens(
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
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

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
        await _create_verified_user_and_get_tokens(
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
        token, _ = await _create_verified_user_and_get_tokens(
            client, "me@example.com", "securepass123"
        )

        resp = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert "id" in data

    async def test_me_without_token_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401


class TestRefresh:
    """Tests for POST /auth/refresh."""

    async def test_refresh_returns_new_token_pair(self, client):
        _, refresh_token = await _create_verified_user_and_get_tokens(
            client, "refresh@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_with_invalid_token_returns_401(self, client):
        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_refresh_with_access_token_returns_401(self, client):
        token, _ = await _create_verified_user_and_get_tokens(
            client, "wrongtype@example.com", "securepass123"
        )

        resp = await client.post(
            "/auth/refresh",
            json={"refresh_token": token},
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
            json={"refresh_token": expired_token},
        )
        assert resp.status_code == 401
