"""Tests for the main app endpoints (root and health)."""


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
