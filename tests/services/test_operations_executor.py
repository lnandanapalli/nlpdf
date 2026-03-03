"""Tests for the operations executor service."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from backend.schemas.compress_schema import CompressParams
from backend.schemas.llm_schema import (
    CompressOperation,
    MergeOperation,
    RotateOperation,
    SplitOperation,
)
from backend.schemas.rotate_schema import RotateParams
from backend.schemas.split_schema import SplitParams
from backend.services.operations_executor_service import execute_operation


class TestExecuteCompressOperation:
    """Tests for compress operation dispatch."""

    def test_calls_compress_pdf(self, sample_pdf, tmp_output):
        op = CompressOperation(operation="compress", parameters=CompressParams(level=1))

        with patch("backend.services.operations_executor_service.compress_pdf") as mock:
            mock.return_value = tmp_output
            result = execute_operation(op, [sample_pdf], tmp_output)

        mock.assert_called_once_with(sample_pdf, tmp_output, 1)
        assert result == tmp_output


class TestExecuteMergeOperation:
    """Tests for merge operation dispatch."""

    def test_calls_merge_pdfs(self, sample_pdf, tmp_output):
        op = MergeOperation(operation="merge", parameters={})
        paths = [sample_pdf, sample_pdf]

        with patch("backend.services.operations_executor_service.merge_pdfs") as mock:
            mock.return_value = tmp_output
            result = execute_operation(op, paths, tmp_output)

        mock.assert_called_once_with(paths, tmp_output)
        assert result == tmp_output

    def test_merge_with_one_file_raises(self, sample_pdf, tmp_output):
        op = MergeOperation(operation="merge", parameters={})

        with pytest.raises(HTTPException) as exc_info:
            execute_operation(op, [sample_pdf], tmp_output)

        assert exc_info.value.status_code == 400
        assert "multiple files" in exc_info.value.detail.lower()


class TestExecuteSplitOperation:
    """Tests for split operation dispatch."""

    def test_calls_split_pdf_merge(self, sample_pdf, tmp_output):
        op = SplitOperation(
            operation="split",
            parameters=SplitParams(page_ranges=[(1, 3)], merge=True),
        )

        with patch("backend.services.operations_executor_service.split_pdf") as mock:
            mock.return_value = tmp_output
            execute_operation(op, [sample_pdf], tmp_output, "doc")

        mock.assert_called_once_with(sample_pdf, [(1, 3)], True, tmp_output, "doc")

    def test_split_no_merge_changes_extension(self, sample_pdf, tmp_output):
        op = SplitOperation(
            operation="split",
            parameters=SplitParams(page_ranges=[(1, 3)], merge=False),
        )

        with patch("backend.services.operations_executor_service.split_pdf") as mock:
            zip_path = tmp_output.with_suffix(".zip")
            mock.return_value = zip_path
            execute_operation(op, [sample_pdf], tmp_output, "doc")

        # Should have been called with .zip extension
        call_args = mock.call_args
        assert call_args[0][3].suffix == ".zip"


class TestExecuteRotateOperation:
    """Tests for rotate operation dispatch."""

    def test_calls_rotate_pdf(self, sample_pdf, tmp_output):
        op = RotateOperation(
            operation="rotate",
            parameters=RotateParams(rotations=[(1, 90)]),
        )

        with patch("backend.services.operations_executor_service.rotate_pdf") as mock:
            mock.return_value = tmp_output
            execute_operation(op, [sample_pdf], tmp_output)

        mock.assert_called_once_with(sample_pdf, [(1, 90)], tmp_output)


class TestErrorHandling:
    """Tests for error handling in execute_operation."""

    def test_value_error_returns_400(self, sample_pdf, tmp_output):
        """ValueError from services should be caught and returned as 400."""
        op = RotateOperation(
            operation="rotate",
            parameters=RotateParams(rotations=[(999, 90)]),
        )

        with patch("backend.services.operations_executor_service.rotate_pdf") as mock:
            mock.side_effect = ValueError("Page 999 exceeds document length")
            with pytest.raises(HTTPException) as exc_info:
                execute_operation(op, [sample_pdf], tmp_output)

        assert exc_info.value.status_code == 400
        assert "page numbers and ranges" in exc_info.value.detail.lower()

    def test_generic_exception_returns_500(self, sample_pdf, tmp_output):
        """Unexpected exceptions should be caught and returned as 500."""
        op = CompressOperation(
            operation="compress",
            parameters=CompressParams(level=2),
        )

        with patch("backend.services.operations_executor_service.compress_pdf") as mock:
            mock.side_effect = RuntimeError("unexpected disk error")
            with pytest.raises(HTTPException) as exc_info:
                execute_operation(op, [sample_pdf], tmp_output)

        assert exc_info.value.status_code == 500
        assert "Something went wrong" in exc_info.value.detail

    def test_http_exception_passes_through(self, sample_pdf, tmp_output):
        """HTTPException from services should pass through unchanged."""
        op = CompressOperation(
            operation="compress",
            parameters=CompressParams(level=2),
        )

        with patch("backend.services.operations_executor_service.compress_pdf") as mock:
            mock.side_effect = HTTPException(status_code=413, detail="File too large")
            with pytest.raises(HTTPException) as exc_info:
                execute_operation(op, [sample_pdf], tmp_output)

        assert exc_info.value.status_code == 413
        assert exc_info.value.detail == "File too large"
