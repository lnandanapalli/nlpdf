"""Alembic migrations, run for real against a scratch SQL Server database.

Catches what the SQLite-based tests can't: a model change without a
migration, a migration that fails on SQL Server, a downgrade that doesn't
work, or two migration heads. Skipped when no SQL Server is reachable.
"""

from collections.abc import Iterator
import os
import subprocess
import sys
import uuid

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
import pytest
from sqlalchemy import URL, create_engine, text

from backend.config import settings
from backend.database import Base
import backend.models  # noqa: F401  (registers every table on the metadata)

# Known, documented drift between the models and the migrations. Anything
# else showing up here means a model changed without a migration.
KNOWN_DRIFT = {
    # documents.owner_id: the model says ondelete=CASCADE; no migration adds it
    # (see the TODO in backend/models/document.py). The ORM cascade covers it.
    ("documents", "owner_id"),
}


def _url(database: str, driver: str = "mssql+pyodbc") -> URL:
    query = {
        "driver": settings.DB_DRIVER,
        "TrustServerCertificate": "yes",
        "Connection Timeout": "5",
    }
    if "18" in settings.DB_DRIVER:
        query["Encrypt"] = "yes"
    return URL.create(
        drivername=driver,
        username=settings.DB_USER,
        password=settings.DB_PASSWORD,
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        database=database,
        query=query,
    )


@pytest.fixture(scope="module")
def scratch_db() -> Iterator[str]:
    """Create an empty database for the test and drop it afterwards."""
    if "sqlite" in (settings.DATABASE_URL_OVERRIDE or ""):
        pytest.skip("migrations target SQL Server")
    admin = create_engine(_url("master"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # no server available in this environment
        admin.dispose()
        pytest.skip(f"SQL Server not reachable: {type(exc).__name__}")

    name = f"nlpdf_migration_test_{uuid.uuid4().hex[:8]}"
    with admin.connect() as conn:
        conn.execute(text(f"CREATE DATABASE [{name}]"))
    try:
        yield name
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"ALTER DATABASE [{name}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
            conn.execute(text(f"DROP DATABASE [{name}]"))
        admin.dispose()


def _alembic(database: str, *args: str) -> None:
    # env.py reads DATABASE_URL_OVERRIDE and swaps the async driver for pyodbc.
    url = _url(database, "mssql+aioodbc").render_as_string(hide_password=False)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        env={**os.environ, "DATABASE_URL_OVERRIDE": url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"alembic {' '.join(args)} failed:\n{result.stderr[-3000:]}"


def _schema_drift(database: str) -> list:
    engine = create_engine(_url(database))
    try:
        with engine.connect() as conn:
            return compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()


def _describe(diff) -> tuple[str, str] | None:
    """Reduce a foreign-key diff to (table, column); None for anything else."""
    if isinstance(diff, tuple) and diff[0] in ("add_fk", "remove_fk"):
        fk = diff[1]
        return (fk.parent.name, next(iter(fk.columns)).name)
    return None


def test_there_is_a_single_migration_head():
    heads = ScriptDirectory.from_config(Config("alembic.ini")).get_heads()
    assert len(heads) == 1, f"multiple heads, merge them: {heads}"


def test_upgrade_matches_the_models(scratch_db):
    _alembic(scratch_db, "upgrade", "head")

    unexpected = []
    for diff in _schema_drift(scratch_db):
        # compare_metadata returns a list of tuples, or lists of tuples for
        # column-level changes; flatten one level.
        for item in diff if isinstance(diff, list) else [diff]:
            if _describe(item) not in KNOWN_DRIFT:
                unexpected.append(item)
    assert not unexpected, "models and migrations disagree:\n" + "\n".join(map(str, unexpected))


def test_downgrade_and_upgrade_again(scratch_db):
    _alembic(scratch_db, "upgrade", "head")
    _alembic(scratch_db, "downgrade", "base")
    _alembic(scratch_db, "upgrade", "head")
