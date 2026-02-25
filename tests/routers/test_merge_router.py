"""Tests for the merge router endpoint."""

from tests.routers.conftest import _pdf_bytes


class TestMergeEndpoint:
    """Tests for POST /pdf/merge."""

    async def test_valid_merge(self, pdf_client):
        pdf1 = _pdf_bytes(2)
        pdf2 = _pdf_bytes(3)
        resp = await pdf_client.post(
            "/pdf/merge",
            files=[
                ("files", ("a.pdf", pdf1, "application/pdf")),
                ("files", ("b.pdf", pdf2, "application/pdf")),
            ],
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_single_file_rejected(self, pdf_client):
        pdf = _pdf_bytes()
        resp = await pdf_client.post(
            "/pdf/merge",
            files=[("files", ("a.pdf", pdf, "application/pdf"))],
        )
        assert resp.status_code == 400
