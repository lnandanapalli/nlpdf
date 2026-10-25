from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.auth.csrf import verify_csrf_token
from backend.crud.user_crud import MAX_FAILED_LOGIN_ATTEMPTS, MAX_OTP_ATTEMPTS
from backend.database import Base, get_db
from backend.models.session import Session
from backend.models.user import User
from backend.routers.auth_router import router as auth_router

# In-memory async SQLite for test isolation
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_auth.db"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


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
    """Replace the real Resend email calls with no-ops."""
    with (
        patch(
            "backend.routers.auth_router.send_otp_email",
            new=MagicMock(),
        ),
        patch(
            "backend.routers.auth_router.send_account_deletion_otp_email",
            new=MagicMock(),
        ),
        patch(
            "backend.routers.auth_router.send_password_reset_otp_email",
            new=MagicMock(),
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _mock_otp():
    """Pin OTP to a known value so tests can verify without reading the hashed DB value."""
    with patch(
        "backend.routers.auth_router.generate_otp",
        return_value=FIXED_OTP,
    ):
        yield


CF_TOKEN = "test-token"
SIGNUP_NAMES = {"first_name": "Test", "last_name": "User"}
FIXED_OTP = "123456"


@pytest.fixture(autouse=True)
async def _setup_db():
    """Create and tear down test tables for each test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
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


def _signup_payload(email, password, **overrides):
    """Build a signup JSON payload with names and cf_token."""
    return {
        "email": email,
        "password": password,
        **SIGNUP_NAMES,
        "cf_token": CF_TOKEN,
        **overrides,
    }


def _verify_payload(email, password, otp_code=FIXED_OTP):
    """Build a verify_otp JSON payload."""
    return {"email": email, "otp_code": otp_code, "password": password, "cf_token": CF_TOKEN}


def _login_payload(email, password):
    """Build a login JSON payload."""
    return {"email": email, "password": password, "cf_token": CF_TOKEN}


async def _create_verified_user_and_get_cookies(client, email, password):
    """Helper: signup, verify OTP, return cookies dict from verify_otp response."""
    await client.post("/auth/signup", json=_signup_payload(email, password))
    resp = await client.post("/auth/verify_otp", json=_verify_payload(email, password))
    assert resp.status_code == 200
    cookies = _extract_cookies(resp)
    return cookies


class TestSignup:
    """Tests for POST /auth/signup."""

    async def test_signup_returns_success(self, client):
        resp = await client.post(
            "/auth/signup",
            json=_signup_payload("new@example.com", "securepass123"),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data
        assert "If that email is valid, a verification code has been sent" in data["message"]

    async def test_signup_duplicate_email_returns_201_if_verified(self, client):
        await _create_verified_user_and_get_cookies(client, "dupe@example.com", "securepass123")

        resp2 = await client.post(
            "/auth/signup",
            json=_signup_payload("dupe@example.com", "securepass123"),
        )
        assert resp2.status_code == 201
        assert "If that email is valid" in resp2.json()["message"]

    async def test_signup_short_password_returns_422(self, client):
        resp = await client.post(
            "/auth/signup",
            json=_signup_payload("short@example.com", "short"),
        )
        assert resp.status_code == 422

    async def test_signup_without_names_returns_422(self, client):
        resp = await client.post(
            "/auth/signup",
            json={
                "email": "noname@example.com",
                "password": "securepass123",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 422

    async def test_signup_stores_names(self, client):
        await client.post(
            "/auth/signup",
            json=_signup_payload("named@example.com", "securepass123"),
        )
        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "named@example.com"))
            user = result.scalars().first()
            assert user is not None
            assert user.first_name == "Test"
            assert user.last_name == "User"


class TestOTP:
    """Tests for POST /auth/verify_otp and /auth/resend_otp."""

    async def test_verify_otp_sets_cookies(self, client):
        email = "otp@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))

        resp = await client.post("/auth/verify_otp", json=_verify_payload(email, "securepass123"))
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
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))

        resp = await client.post(
            "/auth/verify_otp", json=_verify_payload(email, "securepass123", otp_code="000000")
        )
        assert resp.status_code == 401

    async def test_verify_otp_requires_password(self, client):
        email = "nopass@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))

        resp = await client.post(
            "/auth/verify_otp",
            json={"email": email, "otp_code": FIXED_OTP, "cf_token": CF_TOKEN},
        )
        assert resp.status_code == 422

    async def test_otp_attempt_limit_survives_the_error_response(self, client):
        """Each wrong code must be counted even though the request fails.

        get_db rolls back on exceptions, so the counter used to be discarded
        along with the 401 and the limit was never reached.
        """
        email = "otplimit@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))

        for _ in range(MAX_OTP_ATTEMPTS):
            await client.post(
                "/auth/verify_otp", json=_verify_payload(email, "securepass123", otp_code="000000")
            )

        async with TestSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalars().one()
            assert user.otp_attempts == MAX_OTP_ATTEMPTS
            assert user.otp_code is None

        # Even the right code is refused now; a new one has to be requested.
        resp = await client.post("/auth/verify_otp", json=_verify_payload(email, "securepass123"))
        assert resp.status_code in (401, 429)
        assert "access_token" not in _extract_cookies(resp)


class TestPreRegistration:
    """Someone signing up with an address they don't own must not get into it.

    Before the fix the first signup's password stuck: an attacker pre-registered
    victim@ with their own password, the owner verified the emailed code, and
    the attacker could then log in to the owner's verified account.
    """

    async def test_attacker_password_does_not_survive_owner_verification(self, client):
        email = "victim@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "attacker-pass"))
        await client.post("/auth/signup", json=_signup_payload(email, "owner-password"))

        resp = await client.post("/auth/verify_otp", json=_verify_payload(email, "owner-password"))
        assert resp.status_code == 200

        fresh = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with fresh as other:
            owner = await other.post("/auth/login", json=_login_payload(email, "owner-password"))
            attacker = await other.post("/auth/login", json=_login_payload(email, "attacker-pass"))
        assert owner.status_code == 200
        assert attacker.status_code == 401

    async def test_password_given_at_verification_wins(self, client):
        """Even if the attacker signs up last, the code holder sets the password."""
        email = "victim2@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "owner-password"))
        await client.post("/auth/signup", json=_signup_payload(email, "attacker-pass"))

        resp = await client.post("/auth/verify_otp", json=_verify_payload(email, "owner-password"))
        assert resp.status_code == 200

        fresh = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with fresh as other:
            attacker = await other.post("/auth/login", json=_login_payload(email, "attacker-pass"))
            owner = await other.post("/auth/login", json=_login_payload(email, "owner-password"))
        assert attacker.status_code == 401
        assert owner.status_code == 200

    async def test_resignup_replaces_names(self, client):
        email = "renamed@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))
        await client.post(
            "/auth/signup",
            json=_signup_payload(email, "securepass123", first_name="Real", last_name="Owner"),
        )

        async with TestSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalars().one()
            assert (user.first_name, user.last_name) == ("Real", "Owner")

    async def test_resend_otp_success(self, client):
        email = "resend@example.com"
        await client.post("/auth/signup", json=_signup_payload(email, "securepass123"))

        resp = await client.post("/auth/resend_otp", json={"email": email})
        assert resp.status_code == 200
        assert "message" in resp.json()


class TestLogin:
    """Tests for POST /auth/login."""

    async def test_login_sets_cookies(self, client):
        await _create_verified_user_and_get_cookies(client, "login@example.com", "securepass123")

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
            json=_signup_payload("unverified@example.com", "securepass123"),
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
        await _create_verified_user_and_get_cookies(client, "wrong@example.com", "securepass123")

        resp = await client.post(
            "/auth/login",
            json={
                "email": "wrong@example.com",
                "password": "badpassword",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 401


class TestLockout:
    """Repeated wrong passwords must lock the account.

    The failed-login counter is written just before the 401 is raised, and
    get_db rolls back on exceptions, so it used to be discarded every time.
    """

    async def _fail(self, client, email, times):
        for _ in range(times):
            resp = await client.post("/auth/login", json=_login_payload(email, "wrong-password"))
            assert resp.status_code == 401

    async def test_failed_logins_are_counted_and_lock_the_account(self, client):
        email = "lock@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        await self._fail(client, email, MAX_FAILED_LOGIN_ATTEMPTS)

        async with TestSessionLocal() as db:
            user = (await db.execute(select(User).where(User.email == email))).scalars().one()
            assert user.failed_login_attempts == MAX_FAILED_LOGIN_ATTEMPTS
            assert user.locked_until is not None

        # The right password is refused while locked.
        resp = await client.post("/auth/login", json=_login_payload(email, "securepass123"))
        assert resp.status_code == 401
        assert "access_token" not in _extract_cookies(resp)

    async def test_locked_account_looks_like_an_unknown_email(self, client):
        """A distinct 'locked' answer would confirm the address has an account."""
        email = "lock2@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")
        await self._fail(client, email, MAX_FAILED_LOGIN_ATTEMPTS)

        locked = await client.post("/auth/login", json=_login_payload(email, "securepass123"))
        unknown = await client.post(
            "/auth/login", json=_login_payload("nobody@example.com", "securepass123")
        )
        assert locked.status_code == unknown.status_code == 401
        assert locked.json() == unknown.json()

    async def test_password_reset_lifts_the_lock(self, client):
        email = "lock3@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")
        await self._fail(client, email, MAX_FAILED_LOGIN_ATTEMPTS)

        await client.post("/auth/forgot-password", json={"email": email, "cf_token": CF_TOKEN})
        resp = await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass1",  # pragma: allowlist secret
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 200

        resp = await client.post("/auth/login", json=_login_payload(email, "brandnewpass1"))
        assert resp.status_code == 200


class TestMe:
    """Tests for GET /auth/me."""

    async def test_me_returns_user(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "me@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.get("/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert "id" in data
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"

    async def test_me_without_cookie_returns_401(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401


class TestRefresh:
    """Tests for POST /auth/refresh."""

    async def test_refresh_returns_new_cookies(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "refresh@example.com", "securepass123"
        )

        client.cookies.set("refresh_token", cookies["refresh_token"])
        resp = await client.post("/auth/refresh", json={})
        assert resp.status_code == 200
        new_cookies = _extract_cookies(resp)
        assert "access_token" in new_cookies
        assert "refresh_token" in new_cookies
        assert "csrf_token" in new_cookies
        # Body is a SuccessResponse
        data = resp.json()
        assert "message" in data

    async def test_reused_refresh_token_revokes_every_session(self, client):
        """Presenting an already-rotated refresh token signals theft."""
        cookies = await _create_verified_user_and_get_cookies(
            client, "reuse@example.com", "securepass123"
        )
        assert (await client.post("/auth/refresh", json={})).status_code == 200

        # Age the rotation past the grace window for concurrent tabs.
        async with TestSessionLocal() as db:
            await db.execute(
                update(Session).values(last_used_at=datetime.now(UTC) - timedelta(minutes=5))
            )
            await db.commit()

        fresh = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with fresh as thief:
            thief.cookies.set("refresh_token", cookies["refresh_token"])
            assert (await thief.post("/auth/refresh", json={})).status_code == 401

        async with TestSessionLocal() as db:
            remaining = (await db.execute(select(Session))).scalars().all()
            assert remaining == []

    async def test_concurrent_refresh_does_not_revoke_sessions(self, client):
        """Two tabs refreshing at once must not log the user out everywhere."""
        cookies = await _create_verified_user_and_get_cookies(
            client, "tabs@example.com", "securepass123"
        )
        assert (await client.post("/auth/refresh", json={})).status_code == 200

        fresh = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with fresh as other_tab:
            other_tab.cookies.set("refresh_token", cookies["refresh_token"])
            assert (await other_tab.post("/auth/refresh", json={})).status_code == 401

        assert (await client.post("/auth/refresh", json={})).status_code == 200

    async def test_refresh_without_cookie_returns_401(self, client):
        resp = await client.post("/auth/refresh", json={})
        assert resp.status_code == 401

    async def test_refresh_with_access_token_returns_401(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "wrongtype@example.com", "securepass123"
        )

        # Use the access_token as if it were a refresh_token
        client.cookies.set("refresh_token", cookies["access_token"])
        resp = await client.post("/auth/refresh", json={})
        assert resp.status_code == 401

    async def test_refresh_with_expired_token_returns_401(self, client):
        import jwt as pyjwt

        from backend.config import settings

        expired_payload = {
            "sub": "expired@test.com",
            "type": "refresh",
            "exp": datetime(2020, 1, 1, tzinfo=UTC),
        }
        expired_token = pyjwt.encode(
            expired_payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )

        client.cookies.set("refresh_token", expired_token)
        resp = await client.post("/auth/refresh", json={})
        assert resp.status_code == 401


class TestLogout:
    """Tests for POST /auth/logout."""

    async def test_logout_clears_cookies_and_revokes_jti(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "logout@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post("/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Logged out successfully"

        # Verify cookies are cleared (set to empty / max-age=0)
        set_cookies = _extract_cookies(resp)
        for cookie_name in ("access_token", "refresh_token", "csrf_token"):
            # delete_cookie sets value to "" or a deletion marker
            if cookie_name in set_cookies:
                assert set_cookies[cookie_name] in ('""', "", "null")

        # The session row is gone, so the device no longer shows as active
        # and its refresh token can't be used again.
        async with TestSessionLocal() as db:
            remaining = (await db.execute(select(Session))).scalars().all()
            assert remaining == []

    async def test_logout_without_cookie_returns_401(self, client):
        resp = await client.post("/auth/logout")
        assert resp.status_code == 401


class TestUpdateProfile:
    """Tests for PUT /auth/profile."""

    async def test_update_profile_success(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "profile@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.put(
            "/auth/profile",
            json={"first_name": "New", "last_name": "Name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["first_name"] == "New"
        assert data["last_name"] == "Name"

    async def test_update_profile_unauthenticated(self, client):
        resp = await client.put(
            "/auth/profile",
            json={"first_name": "New", "last_name": "Name"},
        )
        assert resp.status_code == 401

    async def test_update_profile_empty_names_returns_422(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "empty@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.put(
            "/auth/profile",
            json={"first_name": "", "last_name": "Name"},
        )
        assert resp.status_code == 422


class TestChangePassword:
    """Tests for POST /auth/change-password."""

    async def test_change_password_success(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "chpw@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": "securepass123",
                "new_password": "newsecurepass456",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Password changed successfully"

        # Verify login with new password works
        login_resp = await client.post(
            "/auth/login",
            json={
                "email": "chpw@example.com",
                "password": "newsecurepass456",
                "cf_token": CF_TOKEN,
            },
        )
        assert login_resp.status_code == 200

    async def test_change_password_wrong_current(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "wrongpw@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": "wrongpassword",
                "new_password": "newsecurepass456",
            },
        )
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    async def test_change_password_same_as_current(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "samepw@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post(
            "/auth/change-password",
            json={"current_password": "securepass123", "new_password": "securepass123"},
        )
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"].lower()

    async def test_change_password_unauthenticated(self, client):
        resp = await client.post(
            "/auth/change-password",
            json={
                "current_password": "securepass123",
                "new_password": "newsecurepass456",
            },
        )
        assert resp.status_code == 401


class TestDeleteAccount:
    """Tests for POST /auth/delete-account/request and /auth/delete-account/confirm."""

    async def test_delete_account_full_flow(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "delete@example.com", "securepass123"
        )

        # Step 1: Request deletion
        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post(
            "/auth/delete-account/request",
            json={"password": "securepass123"},
        )
        assert resp.status_code == 200
        assert "Confirmation code" in resp.json()["message"]

        # Step 2: Confirm deletion (OTP is mocked to FIXED_OTP)
        resp = await client.post(
            "/auth/delete-account/confirm",
            json={"otp_code": FIXED_OTP},
        )
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"].lower()

        # Verify user is gone
        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "delete@example.com"))
            user = result.scalars().first()
            assert user is None

    async def test_delete_account_wrong_password(self, client):
        cookies = await _create_verified_user_and_get_cookies(
            client, "delbadpw@example.com", "securepass123"
        )

        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.post(
            "/auth/delete-account/request",
            json={"password": "wrongpassword"},
        )
        assert resp.status_code == 400

    async def test_delete_account_wrong_otp(self, client):
        await _create_verified_user_and_get_cookies(
            client, "delbadotp@example.com", "securepass123"
        )

        # Request deletion
        await client.post(
            "/auth/delete-account/request",
            json={"password": "securepass123"},
        )

        # Confirm with wrong OTP
        resp = await client.post(
            "/auth/delete-account/confirm",
            json={"otp_code": "000000"},
        )
        assert resp.status_code == 400

    async def test_delete_account_no_active_otp(self, client):
        await _create_verified_user_and_get_cookies(client, "delnootp@example.com", "securepass123")

        resp = await client.post(
            "/auth/delete-account/confirm",
            json={"otp_code": "123456"},
        )
        assert resp.status_code == 400

    async def test_delete_account_expired_otp(self, client):
        await _create_verified_user_and_get_cookies(client, "delexp@example.com", "securepass123")

        # Request deletion
        await client.post(
            "/auth/delete-account/request",
            json={"password": "securepass123"},
        )

        # Manually expire the OTP
        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == "delexp@example.com"))
            user = result.scalars().first()
            assert user is not None
            user.otp_expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()

        resp = await client.post(
            "/auth/delete-account/confirm",
            json={"otp_code": "123456"},
        )
        assert resp.status_code == 400

    async def test_delete_account_unauthenticated(self, client):
        resp = await client.post(
            "/auth/delete-account/request",
            json={"password": "securepass123"},
        )
        assert resp.status_code == 401


class TestForgotPassword:
    """Tests for POST /auth/forgot-password and POST /auth/reset-password."""

    async def test_forgot_password_persists_otp_to_db(self, client):
        """Regression: OTP must be written to DB, not just sent via email."""
        email = "forgot@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        resp = await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )
        assert resp.status_code == 200

        # Verify OTP was persisted to the database
        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            assert user is not None
            assert user.otp_code is not None, "OTP was not persisted to DB"
            assert user.otp_expires_at is not None, "OTP expiry was not set"
            assert user.otp_purpose == "password_reset"
            assert user.otp_attempts == 0

    async def test_forgot_password_nonexistent_email_returns_200(self, client):
        resp = await client.post(
            "/auth/forgot-password",
            json={"email": "nobody@example.com", "cf_token": CF_TOKEN},
        )
        assert resp.status_code == 200
        assert "reset code" in resp.json()["message"]

    async def test_forgot_password_unverified_user_returns_200(self, client):
        await client.post(
            "/auth/signup",
            json=_signup_payload("unverified_forgot@example.com", "securepass123"),
        )
        resp = await client.post(
            "/auth/forgot-password",
            json={"email": "unverified_forgot@example.com", "cf_token": CF_TOKEN},
        )
        assert resp.status_code == 200

    async def test_reset_password_success(self, client):
        email = "reset@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        # Request password reset
        resp = await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )
        assert resp.status_code == 200

        # Reset password with correct OTP
        resp = await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 200
        assert "reset successfully" in resp.json()["message"].lower()

        # Verify login with new password works
        login_resp = await client.post(
            "/auth/login",
            json={"email": email, "password": "brandnewpass456", "cf_token": CF_TOKEN},
        )
        assert login_resp.status_code == 200

    async def test_reset_password_old_password_fails(self, client):
        email = "resetold@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )
        await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )

        # Old password should no longer work
        login_resp = await client.post(
            "/auth/login",
            json={"email": email, "password": "securepass123", "cf_token": CF_TOKEN},
        )
        assert login_resp.status_code == 401

    async def test_reset_password_wrong_otp(self, client):
        email = "wrongotp@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )

        resp = await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": "000000",
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 401

    async def test_reset_password_expired_otp(self, client):
        email = "expiredotp@example.com"
        await _create_verified_user_and_get_cookies(client, email, "securepass123")

        await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )

        # Manually expire the OTP
        async with TestSessionLocal() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalars().first()
            assert user is not None
            user.otp_expires_at = datetime.now(UTC) - timedelta(minutes=1)
            await db.commit()

        resp = await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 401

    async def test_reset_password_nonexistent_email(self, client):
        resp = await client.post(
            "/auth/reset-password",
            json={
                "email": "nobody@example.com",
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )
        assert resp.status_code == 401

    async def test_reset_password_revokes_all_sessions(self, client):
        email = "revoke@example.com"
        cookies = await _create_verified_user_and_get_cookies(client, email, "securepass123")

        await client.post(
            "/auth/forgot-password",
            json={"email": email, "cf_token": CF_TOKEN},
        )
        await client.post(
            "/auth/reset-password",
            json={
                "email": email,
                "otp_code": FIXED_OTP,
                "new_password": "brandnewpass456",
                "cf_token": CF_TOKEN,
            },
        )

        # Old access token should be invalid
        client.cookies.set("access_token", cookies["access_token"])
        resp = await client.get("/auth/me")
        assert resp.status_code == 401


class TestCSRF:
    """Tests for CSRF middleware."""

    @pytest.fixture
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
        resp = await csrf_client.post("/auth/login", json={})
        assert resp.status_code == 200

    async def test_missing_csrf_header_returns_403(self, csrf_client):
        csrf_client.cookies.set("csrf_token", "abc123")
        resp = await csrf_client.post("/protected")
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
        csrf_client.cookies.set("csrf_token", "correct_token")
        resp = await csrf_client.post(
            "/protected",
            headers={"X-CSRF-Token": "wrong_token"},
        )
        assert resp.status_code == 403
        assert "mismatch" in resp.json()["detail"]

    async def test_csrf_match_passes(self, csrf_client):
        from backend.auth.cookies import make_csrf_token

        access = "dummy_access"
        token = make_csrf_token(access)
        csrf_client.cookies.set("csrf_token", token)
        csrf_client.cookies.set("access_token", access)
        resp = await csrf_client.post(
            "/protected",
            headers={"X-CSRF-Token": token},
        )
        assert resp.status_code == 200


class TestSessions:
    """Tests for the session management endpoints.

    These back the 'log out my other devices' flow, so a failure here means a
    user cannot revoke access from a device they no longer control.
    """

    async def test_list_sessions_returns_the_current_one(self, client):
        await _create_verified_user_and_get_cookies(client, "sess@example.com", "securepass123")

        resp = await client.get("/auth/sessions")

        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) == 1
        assert sessions[0]["is_current"] is True

    async def test_list_sessions_requires_authentication(self, client):
        fresh = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with fresh as anon:
            assert (await anon.get("/auth/sessions")).status_code == 401

    async def test_second_login_adds_a_session(self, client):
        await _create_verified_user_and_get_cookies(client, "two@example.com", "securepass123")
        other = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with other as second_device:
            await second_device.post(
                "/auth/login",
                json={
                    "email": "two@example.com",
                    "password": "securepass123",
                    "cf_token": CF_TOKEN,
                },
            )
            listed = (await second_device.get("/auth/sessions")).json()

        assert len(listed) == 2
        assert sum(1 for s in listed if s["is_current"]) == 1

    async def test_terminate_another_session(self, client):
        await _create_verified_user_and_get_cookies(client, "term@example.com", "securepass123")
        other = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with other as second_device:
            await second_device.post(
                "/auth/login",
                json={
                    "email": "term@example.com",
                    "password": "securepass123",
                    "cf_token": CF_TOKEN,
                },
            )

        sessions = (await client.get("/auth/sessions")).json()
        victim = next(s for s in sessions if not s["is_current"])

        resp = await client.delete(f"/auth/sessions/{victim['id']}")
        assert resp.status_code == 200

        remaining = (await client.get("/auth/sessions")).json()
        assert victim["id"] not in [s["id"] for s in remaining]

    async def test_logout_all_revokes_other_devices_but_keeps_the_caller(self, client):
        """logout-all re-issues tokens for the calling device by design.

        It revokes every session and bumps token_version, then logs this device
        straight back in -- hence "all *other* sessions". The caller staying
        signed in is the contract, not a leak.
        """
        await _create_verified_user_and_get_cookies(client, "all@example.com", "securepass123")
        other = AsyncClient(transport=ASGITransport(app=app_instance), base_url="http://test")
        async with other as second_device:
            await second_device.post(
                "/auth/login",
                json={
                    "email": "all@example.com",
                    "password": "securepass123",
                    "cf_token": CF_TOKEN,
                },
            )
            assert (await second_device.get("/auth/me")).status_code == 200

            resp = await client.post("/auth/sessions/logout-all")
            assert resp.status_code == 200

            # The other device's access token is invalidated by the version bump.
            assert (await second_device.get("/auth/me")).status_code == 401

        # The caller is still signed in, holding the only remaining session.
        assert (await client.get("/auth/me")).status_code == 200
        assert len((await client.get("/auth/sessions")).json()) == 1
