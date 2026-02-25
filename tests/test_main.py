"""Tests for the main app endpoints (root and health)."""

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app as main_app


@pytest.fixture()
async def client():
    """Async test client for the main app."""
    transport = ASGITransport(app=main_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestRootAndHealth:
    """Tests for / and /health endpoints."""

    async def test_root(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert resp.json()["message"] == "NLPDF API is running"

    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
