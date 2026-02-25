"""Tests for the split router endpoint."""

from tests.routers.conftest import _pdf_bytes


class TestSplitEndpoint:
    """Tests for POST /pdf/split."""

    async def test_split_merge(self, pdf_client):
        pdf = _pdf_bytes(5)
        resp = await pdf_client.post(
            "/pdf/split",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"page_ranges": "[[1, 3]]", "merge": "true"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"

    async def test_split_no_merge_returns_zip(self, pdf_client):
        pdf = _pdf_bytes(5)
        resp = await pdf_client.post(
            "/pdf/split",
            files={"file": ("test.pdf", pdf, "application/pdf")},
            data={"page_ranges": "[[1, 2], [4, 5]]", "merge": "false"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
