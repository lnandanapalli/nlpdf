"""Shared pytest fixtures for the NLPDF test suite."""

import io
import logging
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
import pytest


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a real 5-page PDF for testing."""
    pdf_path = tmp_path / "sample.pdf"
    writer = PdfWriter()
    for _ in range(5):
        writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def small_pdf(tmp_path: Path) -> Path:
    """Create a single-page PDF for simple tests."""
    pdf_path = tmp_path / "small.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Provide a temporary output path."""
    return tmp_path / "output.pdf"


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    """Build the database schema before running tests."""
    from backend.base import Base
    from backend.database import engine

    # Only auto-create tables if we are using an in-memory SQLite DB
    # or a dedicated test DB path.
    if "sqlite" in str(engine.url):
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


@pytest.fixture
def pdf_bytes(small_pdf: Path) -> bytes:
    """Return raw bytes of a valid single-page PDF."""
    return small_pdf.read_bytes()


@pytest.fixture
async def client():
    """Async test client bound to the real application."""
    from backend.main import app as main_app

    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def captured_logs():
    """Capture everything written to the root logger, tracebacks included.

    Asserting against real emitted text rather than a patched logger means the
    check still holds if logging moves to another module or another sink.
    """
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.DEBUG)
    root = logging.getLogger()
    previous_level = root.level
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)
