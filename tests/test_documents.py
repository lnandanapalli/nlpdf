"""Tests for the document history endpoints."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.auth.dependencies import get_current_user
from backend.crud.document_crud import create_document
from backend.database import Base, get_db
from backend.models.document import Document
from backend.models.user import User
from backend.routers.document_router import router as document_router

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_documents.db"

test_engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

OWNER_ID = 1
INTRUDER_ID = 2


async def _override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _build_app(user_id: int) -> FastAPI:
    app = FastAPI()
    app.include_router(document_router)
    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: User(
        id=user_id,
        email=f"user{user_id}@example.com",
        hashed_password="x",  # pragma: allowlist secret
    )
    return app


@pytest.fixture(autouse=True)
async def _setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def owner_client():
    """Client authenticated as the user who owns the seeded documents."""
    transport = ASGITransport(app=_build_app(OWNER_ID))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def intruder_client():
    """Client authenticated as a different user."""
    transport = ASGITransport(app=_build_app(INTRUDER_ID))
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _seed(count: int, owner_id: int = OWNER_ID) -> list[int]:
    """Insert `count` documents for a user, returning their ids oldest-first."""
    ids = []
    async with TestSessionLocal() as session:
        session.add(
            User(
                id=owner_id,
                email=f"user{owner_id}@example.com",
                hashed_password="x",  # pragma: allowlist secret
            )
        )
        await session.flush()
        for index in range(count):
            doc = await create_document(
                db=session,
                owner_id=owner_id,
                original_filename=f"file{index}.pdf",
                operation_type="compress",
                page_count=index + 1,
            )
            ids.append(doc.id)
        await session.commit()
    return ids


class TestListDocuments:
    """GET /documents."""

    async def test_empty_history(self, owner_client):
        await _seed(0)
        resp = await owner_client.get("/documents")

        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    async def test_returns_owned_documents(self, owner_client):
        await _seed(3)
        resp = await owner_client.get("/documents")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert {item["original_filename"] for item in body["items"]} == {
            "file0.pdf",
            "file1.pdf",
            "file2.pdf",
        }

    async def test_newest_first(self, owner_client):
        ids = await _seed(3)
        resp = await owner_client.get("/documents")

        returned = [item["id"] for item in resp.json()["items"]]
        assert returned == sorted(ids, reverse=True)

    async def test_pagination(self, owner_client):
        await _seed(5)
        resp = await owner_client.get("/documents", params={"limit": 2, "offset": 2})

        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5  # total is the full count, not the page
        assert body["limit"] == 2
        assert body["offset"] == 2

    async def test_rejects_out_of_range_limit(self, owner_client):
        await _seed(1)
        assert (await owner_client.get("/documents", params={"limit": 0})).status_code == 422
        assert (await owner_client.get("/documents", params={"limit": 500})).status_code == 422
        assert (await owner_client.get("/documents", params={"offset": -1})).status_code == 422

    async def test_does_not_leak_other_users_documents(self, intruder_client):
        await _seed(3, owner_id=OWNER_ID)
        resp = await intruder_client.get("/documents")

        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0


class TestDeleteDocument:
    """DELETE /documents/{id}."""

    async def test_deletes_own_document(self, owner_client):
        ids = await _seed(2)
        resp = await owner_client.delete(f"/documents/{ids[0]}")

        assert resp.status_code == 200
        remaining = (await owner_client.get("/documents")).json()
        assert remaining["total"] == 1
        assert ids[0] not in [item["id"] for item in remaining["items"]]

    async def test_missing_document_is_404(self, owner_client):
        await _seed(1)
        assert (await owner_client.delete("/documents/999999")).status_code == 404

    async def test_cannot_delete_another_users_document(self, intruder_client):
        ids = await _seed(1, owner_id=OWNER_ID)
        resp = await intruder_client.delete(f"/documents/{ids[0]}")

        # Indistinguishable from "no such id", so ids cannot be enumerated.
        assert resp.status_code == 404

        async with TestSessionLocal() as session:
            survivor = await session.get(Document, ids[0])
            assert survivor is not None, "another user's document was deleted"


class TestClearDocuments:
    """DELETE /documents."""

    async def test_clears_only_callers_history(self, owner_client, intruder_client):
        await _seed(3, owner_id=OWNER_ID)
        await _seed(2, owner_id=INTRUDER_ID)

        resp = await owner_client.delete("/documents")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 3

        assert (await owner_client.get("/documents")).json()["total"] == 0
        assert (await intruder_client.get("/documents")).json()["total"] == 2

    async def test_clearing_empty_history_is_a_no_op(self, owner_client):
        await _seed(0)
        resp = await owner_client.delete("/documents")

        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0
