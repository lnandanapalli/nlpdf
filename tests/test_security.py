"""Tests for security utilities."""

import io
from unittest.mock import MagicMock

from fastapi import HTTPException, UploadFile
import pytest

from backend.security import (
    MAX_FILE_SIZE_BYTES,
    MAX_MARKDOWN_SIZE_BYTES,
    cleanup_files,
    get_client_ip,
    validate_and_save_markdown,
    validate_and_save_pdf,
)

# ── validate_and_save_pdf ────────────────────────────────────────────────────


class TestValidateAndSavePdf:
    """Tests for validate_and_save_pdf."""

    async def test_valid_pdf_saved(self, pdf_bytes, tmp_path):
        dest = tmp_path / "saved.pdf"
        upload = UploadFile(file=io.BytesIO(pdf_bytes), filename="test.pdf")

        await validate_and_save_pdf(upload, dest)

        assert dest.exists()

        # The sanitization step modifies the exact byte structure.
        # Instead of strict byte matching, assert that it remains a completely valid PDF.
        import pikepdf

        with pikepdf.open(dest):
            pass

    async def test_not_a_pdf_raises(self, tmp_path):
        dest = tmp_path / "not_a_pdf.pdf"
        upload = UploadFile(file=io.BytesIO(b"not a pdf"), filename="bad.txt")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_pdf(upload, dest)

        assert exc_info.value.status_code == 400
        assert "not a valid PDF" in exc_info.value.detail
        # File should be cleaned up (or never created)
        assert not dest.exists()

    async def test_empty_file_raises(self, tmp_path):
        dest = tmp_path / "empty.pdf"
        upload = UploadFile(file=io.BytesIO(b""), filename="empty.pdf")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_pdf(upload, dest)

        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    async def test_oversized_file_raises(self, tmp_path):
        dest = tmp_path / "oversized.pdf"
        # Create content that starts with PDF magic bytes but exceeds max size
        content = b"%PDF-" + b"x" * MAX_FILE_SIZE_BYTES
        upload = UploadFile(file=io.BytesIO(content), filename="big.pdf")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_pdf(upload, dest)

        assert exc_info.value.status_code == 413
        assert "exceeds maximum size" in exc_info.value.detail


# ── validate_and_save_markdown ────────────────────────────────────────────────


class TestValidateAndSaveMarkdown:
    """Tests for validate_and_save_markdown."""

    async def test_valid_markdown_saved(self, tmp_path):
        dest = tmp_path / "saved.md"
        content = b"# Hello\n\nSome **bold** text."
        upload = UploadFile(file=io.BytesIO(content), filename="test.md")

        await validate_and_save_markdown(upload, dest)

        assert dest.exists()
        assert dest.read_bytes() == content

    async def test_empty_markdown_raises(self, tmp_path):
        dest = tmp_path / "empty.md"
        upload = UploadFile(file=io.BytesIO(b""), filename="empty.md")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_markdown(upload, dest)

        assert exc_info.value.status_code == 400
        assert "empty" in exc_info.value.detail.lower()

    async def test_invalid_utf8_raises(self, tmp_path):
        dest = tmp_path / "bad.md"
        content = b"\xff\xfe invalid utf-8 \x80\x81"
        upload = UploadFile(file=io.BytesIO(content), filename="bad.md")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_markdown(upload, dest)

        assert exc_info.value.status_code == 400
        assert "not valid UTF-8" in exc_info.value.detail
        assert not dest.exists()

    async def test_oversized_markdown_raises(self, tmp_path):
        dest = tmp_path / "oversized.md"
        content = b"x" * (MAX_MARKDOWN_SIZE_BYTES + 1)
        upload = UploadFile(file=io.BytesIO(content), filename="big.md")

        with pytest.raises(HTTPException) as exc_info:
            await validate_and_save_markdown(upload, dest)

        assert exc_info.value.status_code == 413
        assert "exceeds maximum size" in exc_info.value.detail


# ── cleanup_files ────────────────────────────────────────────────────────────


class TestCleanupFiles:
    """Tests for cleanup_files."""

    def test_deletes_existing_files(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")

        cleanup_files(f1, f2)

        assert not f1.exists()
        assert not f2.exists()

    def test_missing_files_dont_raise(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        cleanup_files(missing)  # should not raise


# ── get_client_ip ────────────────────────────────────────────────────────────


class TestGetClientIp:
    """Tests for get_client_ip."""

    def test_from_x_forwarded_for(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        # Uses rightmost IP (appended by reverse proxy, not spoofable)
        assert get_client_ip(request) == "5.6.7.8"

    def test_from_request_client(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        assert get_client_ip(request) == "192.168.1.1"

    def test_unknown_fallback(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert get_client_ip(request) == "unknown"
