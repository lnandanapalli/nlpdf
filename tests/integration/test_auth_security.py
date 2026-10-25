"""Security properties of the auth flows, exercised through the full app."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy import select

from backend.config import settings
from backend.models.session import Session
from tests.integration.conftest import (
    PASSWORD,
    SessionLocal,
    new_client,
    sign_up_and_verify,
    use_csrf,
)

SIGNUP = {"first_name": "A", "last_name": "B", "cf_token": "t"}


def replace_cookie(client, name: str, value: str) -> None:
    """Swap a cookie's value in place; cookies.set() would add a duplicate."""
    for cookie in client.cookies.jar:
        if cookie.name == name:
            cookie.value = value
            return
    raise AssertionError(f"{name} is not set")


def cookie_attrs(resp, name: str) -> str:
    """The raw Set-Cookie header for one cookie, lower-cased."""
    for header in resp.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header.lower()
    raise AssertionError(f"{name} was not set")


class TestNoAccountEnumeration:
    """Responses must not reveal whether an address has an account."""

    async def test_signup_answers_the_same_for_new_and_existing_addresses(self, anon, outbox):
        async with new_client() as owner:
            await sign_up_and_verify(owner, outbox, "taken@example.com")
        outbox.clear()

        taken = await anon.post(
            "/auth/signup", json={"email": "taken@example.com", "password": PASSWORD, **SIGNUP}
        )
        fresh = await anon.post(
            "/auth/signup", json={"email": "fresh@example.com", "password": PASSWORD, **SIGNUP}
        )
        assert (taken.status_code, taken.json()) == (fresh.status_code, fresh.json())
        # The verified owner is not emailed a code; only the new address is.
        assert set(outbox) == {"fresh@example.com"}

    @pytest.mark.parametrize(
        ("path", "extra"),
        [("/auth/forgot-password", {"cf_token": "t"}), ("/auth/resend_otp", {})],
    )
    async def test_code_requests_answer_the_same(self, anon, outbox, path, extra):
        async with new_client() as owner:
            await sign_up_and_verify(owner, outbox, "real@example.com")

        real = await anon.post(path, json={"email": "real@example.com", **extra})
        ghost = await anon.post(path, json={"email": "ghost@example.com", **extra})
        assert (real.status_code, real.json()) == (ghost.status_code, ghost.json())

    async def test_login_answers_the_same_for_unknown_wrong_and_locked(self, anon, outbox):
        async with new_client() as owner:
            await sign_up_and_verify(owner, outbox, "victim@example.com")

        def attempt(email, password):
            return anon.post(
                "/auth/login", json={"email": email, "password": password, "cf_token": "t"}
            )

        unknown = await attempt("nobody@example.com", "whatever-pass")
        wrong = await attempt("victim@example.com", "whatever-pass")
        for _ in range(5):
            await attempt("victim@example.com", "whatever-pass")
        locked = await attempt("victim@example.com", PASSWORD)

        bodies = {(r.status_code, r.text) for r in (unknown, wrong, locked)}
        assert len(bodies) == 1


class TestCookies:
    async def test_auth_cookies_are_locked_down(self, anon, outbox):
        with patch("backend.auth.cookies.settings.COOKIE_SECURE", True):
            await anon.post(
                "/auth/signup", json={"email": "c@example.com", "password": PASSWORD, **SIGNUP}
            )
            resp = await anon.post(
                "/auth/verify_otp",
                json={
                    "email": "c@example.com",
                    "otp_code": outbox["c@example.com"],
                    "password": PASSWORD,
                    "cf_token": "t",
                },
            )

        access = cookie_attrs(resp, "access_token")
        refresh = cookie_attrs(resp, "refresh_token")
        csrf = cookie_attrs(resp, "csrf_token")
        for cookie in (access, refresh, csrf):
            assert "secure" in cookie
            assert "samesite=lax" in cookie
        assert "httponly" in access
        assert "httponly" in refresh
        assert "httponly" not in csrf  # the frontend must read it
        # The long-lived token is only ever sent to the one route that needs it.
        assert "path=/auth/refresh" in refresh

    async def test_tokens_are_not_in_response_bodies(self, user):
        resp = await user.get("/auth/me")
        assert "token" not in resp.text.lower()
        assert "hashed_password" not in resp.text


class TestTokens:
    async def test_tampered_access_token_is_rejected(self, user):
        token = user.cookies["access_token"]
        replace_cookie(
            user, "access_token", token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1]
        )
        assert (await user.get("/auth/me")).status_code == 401

    async def test_token_signed_with_another_key_is_rejected(self, user):
        forged = jwt.encode(
            {
                "sub": "owner@example.com",
                "type": "access",
                "ver": 0,
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            "not-the-server-secret-but-long-enough-0123456789",
            algorithm="HS256",
        )
        replace_cookie(user, "access_token", forged)
        assert (await user.get("/auth/me")).status_code == 401

    async def test_unsigned_token_is_rejected(self, user):
        forged = jwt.encode(
            {"sub": "owner@example.com", "type": "access", "ver": 0}, key=None, algorithm="none"
        )
        replace_cookie(user, "access_token", forged)
        assert (await user.get("/auth/me")).status_code == 401

    async def test_refresh_token_cannot_be_used_as_an_access_token(self, user):
        refresh = jwt.decode(
            user.cookies["refresh_token"], settings.JWT_SECRET_KEY, algorithms=["HS256"]
        )
        assert refresh["type"] == "refresh"
        replace_cookie(user, "access_token", user.cookies["refresh_token"])
        assert (await user.get("/auth/me")).status_code == 401

    async def test_expired_access_token_is_renewed_by_refresh(self, user):
        expired = jwt.encode(
            {
                "sub": "owner@example.com",
                "type": "access",
                "ver": 0,
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        replace_cookie(user, "access_token", expired)
        assert (await user.get("/auth/me")).status_code == 401

        assert (await user.post("/auth/refresh", json={})).status_code == 200
        use_csrf(user)
        assert (await user.get("/auth/me")).status_code == 200


class TestIsolationBetweenUsers:
    async def test_cannot_end_another_users_session(self, user, outbox):
        async with new_client() as other:
            await sign_up_and_verify(other, outbox, "other@example.com")
            [theirs] = (await other.get("/auth/sessions")).json()

            resp = await user.delete(f"/auth/sessions/{theirs['id']}")
            assert resp.status_code == 200  # no oracle for which ids exist...
            assert (await other.get("/auth/me")).status_code == 200  # ...and nothing happened

        async with SessionLocal() as db:
            assert await db.get(Session, theirs["id"]) is not None

    async def test_sessions_list_shows_only_your_own(self, user, outbox):
        async with new_client() as other:
            await sign_up_and_verify(other, outbox, "other2@example.com")
        mine = (await user.get("/auth/sessions")).json()
        assert len(mine) == 1

    async def test_account_deletion_removes_sessions(self, user, outbox):
        assert (
            await user.post("/auth/delete-account/request", json={"password": PASSWORD})
        ).status_code == 200
        code = outbox["owner@example.com"]
        resp = await user.post("/auth/delete-account/confirm", json={"otp_code": code})
        assert resp.status_code == 200

        async with SessionLocal() as db:
            assert (await db.execute(select(Session))).scalars().all() == []
        assert (await user.get("/auth/me")).status_code == 401


class TestCodePurposes:
    """A code issued for one purpose can't be spent on another."""

    async def test_deletion_code_cannot_reset_the_password(self, user, anon, outbox):
        await user.post("/auth/delete-account/request", json={"password": PASSWORD})
        code = outbox["owner@example.com"]

        resp = await anon.post(
            "/auth/reset-password",
            json={
                "email": "owner@example.com",
                "otp_code": code,
                "new_password": "taken-over-123",  # pragma: allowlist secret
                "cf_token": "t",
            },
        )
        assert resp.status_code == 401

    async def test_reset_code_cannot_delete_the_account(self, user, anon, outbox):
        await anon.post(
            "/auth/forgot-password", json={"email": "owner@example.com", "cf_token": "t"}
        )
        code = outbox["owner@example.com"]

        resp = await user.post("/auth/delete-account/confirm", json={"otp_code": code})
        assert resp.status_code == 400
        assert (await user.get("/auth/me")).status_code == 200

    async def test_a_code_works_only_once(self, anon, outbox):
        async with new_client() as owner:
            await sign_up_and_verify(owner, outbox, "once@example.com")
        await anon.post(
            "/auth/forgot-password", json={"email": "once@example.com", "cf_token": "t"}
        )
        body = {
            "email": "once@example.com",
            "otp_code": outbox["once@example.com"],
            "new_password": "first-new-pass-1",  # pragma: allowlist secret
            "cf_token": "t",
        }
        assert (await anon.post("/auth/reset-password", json=body)).status_code == 200
        body["new_password"] = "second-new-pass-2"  # pragma: allowlist secret
        assert (await anon.post("/auth/reset-password", json=body)).status_code == 401

    async def test_expired_code_is_refused(self, anon, outbox):
        await anon.post(
            "/auth/signup", json={"email": "late@example.com", "password": PASSWORD, **SIGNUP}
        )
        later = datetime.now(UTC) + timedelta(minutes=11)
        with patch("backend.routers.auth_router.datetime") as fake_dt:
            fake_dt.now.return_value = later
            resp = await anon.post(
                "/auth/verify_otp",
                json={
                    "email": "late@example.com",
                    "otp_code": outbox["late@example.com"],
                    "password": PASSWORD,
                    "cf_token": "t",
                },
            )
        assert resp.status_code == 401
