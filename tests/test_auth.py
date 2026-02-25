"""Integration tests for auth endpoints (signup, login, me).

These tests use an in-memory SQLite database to avoid requiring PostgreSQL.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.routers.auth_router import router as auth_router

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


class TestSignup:
    """Tests for POST /auth/signup."""

    async def test_signup_returns_token(self, client):
        resp = await client.post(
            "/auth/signup",
            json={"email": "new@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_signup_duplicate_email_returns_409(self, client):
        payload = {"email": "dupe@example.com", "password": "securepass123"}
        resp1 = await client.post("/auth/signup", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/auth/signup", json=payload)
        assert resp2.status_code == 409

    async def test_signup_short_password_returns_422(self, client):
        resp = await client.post(
            "/auth/signup",
            json={"email": "short@example.com", "password": "short"},
        )
        assert resp.status_code == 422

    async def test_signup_invalid_email_returns_422(self, client):
        resp = await client.post(
            "/auth/signup",
            json={"email": "not-an-email", "password": "securepass123"},
        )
        assert resp.status_code == 422


class TestLogin:
    """Tests for POST /auth/login."""

    async def test_login_success(self, client):
        # First signup
        await client.post(
            "/auth/signup",
            json={"email": "login@example.com", "password": "securepass123"},
        )

        # Then login
        resp = await client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "securepass123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_wrong_password_returns_401(self, client):
        await client.post(
            "/auth/signup",
            json={"email": "wrong@example.com", "password": "securepass123"},
        )

        resp = await client.post(
            "/auth/login",
            json={"email": "wrong@example.com", "password": "badpassword"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_user_returns_401(self, client):
        resp = await client.post(
            "/auth/login",
            json={"email": "noone@example.com", "password": "anything"},
        )
        assert resp.status_code == 401


class TestMe:
    """Tests for GET /auth/me."""

    async def test_me_returns_user(self, client):
        resp = await client.post(
            "/auth/signup",
            json={"email": "me@example.com", "password": "securepass123"},
        )
        token = resp.json()["access_token"]

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

    async def test_me_with_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401
