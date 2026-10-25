"""Startup and periodic housekeeping in backend.main."""

import asyncio
from datetime import UTC, datetime, timedelta
import os
import time
from unittest.mock import patch

from fastapi import FastAPI
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend import main
from backend.database import Base
from backend.models.session import Session
from backend.models.user import User

engine = create_async_engine("sqlite+aiosqlite:///./test_lifecycle.db")
TestSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


def _age(path, seconds: int) -> None:
    past = time.time() - seconds
    os.utime(path, (past, past))


class TestCleanupOldUploads:
    def test_removes_only_stale_files_and_dirs(self, tmp_path):
        stale_file = tmp_path / "old.pdf"
        stale_dir = tmp_path / "olddir"
        fresh_file = tmp_path / "new.pdf"
        stale_file.write_bytes(b"x")
        stale_dir.mkdir()
        (stale_dir / "inner.pdf").write_bytes(b"x")
        fresh_file.write_bytes(b"x")
        _age(stale_file, 7200)
        _age(stale_dir, 7200)

        with patch.object(main, "UPLOAD_DIR", tmp_path):
            main._cleanup_old_uploads(max_age_seconds=3600)

        assert not stale_file.exists()
        assert not stale_dir.exists()
        assert fresh_file.exists()

    def test_missing_upload_dir_is_fine(self, tmp_path):
        with patch.object(main, "UPLOAD_DIR", tmp_path / "does-not-exist"):
            main._cleanup_old_uploads()


class TestCleanupExpiredSessions:
    @pytest.fixture(autouse=True)
    async def _db(self):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def test_deletes_expired_rows_and_keeps_live_ones(self):
        now = datetime.now(UTC)
        async with TestSessionLocal() as db:
            db.add(
                User(id=1, email="u@example.com", hashed_password="x")
            )  # pragma: allowlist secret
            db.add(Session(user_id=1, jti="expired", expires_at=now - timedelta(days=1)))
            db.add(Session(user_id=1, jti="live", expires_at=now + timedelta(days=1)))
            await db.commit()

        with patch.object(main, "AsyncSessionLocal", TestSessionLocal):
            await main._cleanup_expired_sessions()

        async with TestSessionLocal() as db:
            jtis = (await db.execute(select(Session.jti))).scalars().all()
        assert jtis == ["live"]

    async def test_database_errors_are_logged_not_raised(self, captured_logs):
        def broken():
            raise RuntimeError("db down")

        with patch.object(main, "AsyncSessionLocal", broken):
            await main._cleanup_expired_sessions()
        assert "session_cleanup_error" in captured_logs.getvalue()


async def test_periodic_cleanup_survives_a_failing_step(captured_logs):
    """One failing housekeeping step must not kill the loop or the others."""
    sessions_cleaned = asyncio.Event()

    async def mark_sessions_cleaned():
        sessions_cleaned.set()

    with (
        patch.object(main, "_cleanup_old_uploads", side_effect=OSError("disk")),
        patch.object(main, "_cleanup_expired_sessions", side_effect=mark_sessions_cleaned),
    ):
        task = asyncio.create_task(main._periodic_cleanup(interval_seconds=0))
        await asyncio.wait_for(sessions_cleaned.wait(), timeout=2)
        task.cancel()

    assert "periodic_cleanup_error" in captured_logs.getvalue()


async def test_lifespan_starts_and_stops_the_cleanup_task():
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_periodic():
        started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    with (
        patch.object(main, "_cleanup_old_uploads") as uploads,
        patch.object(main, "_periodic_cleanup", fake_periodic),
    ):
        async with main.lifespan(FastAPI()):
            await asyncio.wait_for(started.wait(), timeout=2)
            uploads.assert_called_once()
    assert cancelled.is_set()
