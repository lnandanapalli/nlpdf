"""Shared fixtures for router integration tests."""

import io

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter

from backend.routers.compress_router import router as compress_router
from backend.routers.merge_router import router as merge_router
from backend.routers.rotate_router import router as rotate_router
from backend.routers.split_router import router as split_router


def _create_test_app() -> FastAPI:
    """Build a minimal FastAPI app with all PDF routers for testing."""
    test_app = FastAPI()
    test_app.include_router(compress_router)
    test_app.include_router(merge_router)
    test_app.include_router(rotate_router)
    test_app.include_router(split_router)
    return test_app


@pytest.fixture()
async def pdf_client():
    """Async test client with all PDF routers registered."""
    test_app = _create_test_app()
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _pdf_bytes(pages: int = 1) -> bytes:
    """Generate a valid PDF with the given number of blank pages."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
