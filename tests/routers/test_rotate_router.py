"""Tests for the rotate router endpoint."""

from tests.routers.conftest import _pdf_bytes


class TestRotateEndpoint:
    """Tests for POST /pdf/rotate."""

    async def test_valid_rotate(self, pdf_client):
        pdf = _pdf_bytes(3)
        resp = await pdf_client.post(
            "/pdf/rotate",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"rotations": "[[1, 90], [3, 180]]"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_invalid_json_rotations(self, pdf_client):
        pdf = _pdf_bytes()
        resp = await pdf_client.post(
            "/pdf/rotate",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"rotations": "not json"},
        )
        assert resp.status_code == 400
