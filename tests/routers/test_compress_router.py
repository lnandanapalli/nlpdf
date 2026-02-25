"""Tests for the compress router endpoint."""

from tests.routers.conftest import _pdf_bytes


class TestCompressEndpoint:
    """Tests for POST /pdf/compress."""

    async def test_valid_compress(self, pdf_client):
        pdf = _pdf_bytes(2)
        resp = await pdf_client.post(
            "/pdf/compress",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"level": "2"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_invalid_level(self, pdf_client):
        pdf = _pdf_bytes()
        resp = await pdf_client.post(
            "/pdf/compress",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"level": '"invalid"'},
        )
        assert resp.status_code == 422
