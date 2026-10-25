"""Fixtures for integration tests against the full application.

Unlike the router-level tests, these go through backend.main.app as deployed:
every middleware (CSRF, CORS, security headers, timeout), every router and the
real PDF pipeline. Only the edges are replaced: the database is a throwaway
SQLite file, the LLM is scripted, and email/Turnstile are stubbed.
"""

from collections.abc import AsyncIterator, Iterator
import io
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import Base, get_db
from backend.main import app
from backend.schemas.llm_schema import OperationType, validate_llm_json_list
from backend.services.llm_service import get_llm_service

DB_PATH = Path("test_integration.db")
engine = create_async_engine(f"sqlite+aiosqlite:///./{DB_PATH}")
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

PASSWORD = "integration-pass-1"  # pragma: allowlist secret
ORIGIN = "http://localhost:5173"  # one of the default CORS origins


async def _override_get_db() -> AsyncIterator[AsyncSession]:
    # Same commit/rollback contract as backend.database.get_db.
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class ScriptedLLM:
    """Stands in for LLMService: returns whatever operations a test scripts.

    The script is raw JSON-like dicts, validated by the real schema code, so a
    test can also hand back operations the real model might hallucinate.
    """

    def __init__(self) -> None:
        self.plan: list[dict[str, Any]] = [{"operation": "compress", "parameters": {"level": 2}}]
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    async def process_message(
        self, user_message: str, pdf_metadata: dict[str, Any] | None = None
    ) -> list[OperationType]:
        self.calls.append({"message": user_message, "metadata": pdf_metadata})
        if self.error is not None:
            raise self.error
        return validate_llm_json_list(self.plan)


@pytest.fixture(autouse=True)
async def _database() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def llm() -> Iterator[ScriptedLLM]:
    scripted = ScriptedLLM()
    app.dependency_overrides[get_llm_service] = lambda: scripted
    yield scripted
    app.dependency_overrides.pop(get_llm_service, None)


@pytest.fixture(autouse=True)
def outbox() -> Iterator[dict[str, str]]:
    """Codes 'emailed' during the test, by address. Turnstile always passes."""
    sent: dict[str, str] = {}

    def capture(to_email: str, otp_code: str) -> None:
        sent[to_email] = otp_code

    with (
        patch("backend.routers.auth_router.verify_turnstile", new=AsyncMock(return_value=True)),
        patch("backend.routers.auth_router.send_otp_email", new=capture),
        patch("backend.routers.auth_router.send_password_reset_otp_email", new=capture),
        patch("backend.routers.auth_router.send_account_deletion_otp_email", new=capture),
    ):
        yield sent


def make_pdf(pages: int) -> bytes:
    """A real blank PDF with the given number of pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def new_client() -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Origin": ORIGIN},
    )


@pytest.fixture
async def anon() -> AsyncIterator[AsyncClient]:
    async with new_client() as client:
        yield client


async def sign_up_and_verify(
    client: AsyncClient, outbox: dict[str, str], email: str, password: str = PASSWORD
) -> AsyncClient:
    """Create a verified account; the client ends up signed in with CSRF set."""
    body = {
        "email": email,
        "password": password,
        "first_name": "Int",
        "last_name": "Test",
        "cf_token": "t",
    }
    assert (await client.post("/auth/signup", json=body)).status_code == 201
    verify = {"email": email, "otp_code": outbox[email], "password": password, "cf_token": "t"}
    resp = await client.post("/auth/verify_otp", json=verify)
    assert resp.status_code == 200, resp.text
    use_csrf(client)
    return client


def use_csrf(client: AsyncClient) -> None:
    """Copy the csrf cookie into the header, as the frontend does."""
    client.headers["X-CSRF-Token"] = client.cookies["csrf_token"]


@pytest.fixture
async def user(outbox: dict[str, str]) -> AsyncIterator[AsyncClient]:
    """A signed-in client for a fresh account."""
    async with new_client() as client:
        yield await sign_up_and_verify(client, outbox, "owner@example.com")
