"""Tests for the operations executor service."""

from unittest.mock import patch

from fastapi import HTTPException
import pytest

from backend.schemas.compress_schema import CompressParams
from backend.schemas.llm_schema import (
    CompressOperation,
    MergeOperation,
    RotateOperation,
    SplitOperation,
)
from backend.schemas.rotate_schema import RotateParams
from backend.schemas.split_schema import SplitParams
from backend.services.operations_executor_service import (
    execute_operation,
    execute_operation_chain,
    validate_operation_chain,
)

ROTATE = RotateOperation(operation="rotate", parameters=RotateParams(rotations=[(1, 90)]))
SPLIT = SplitOperation(operation="split", parameters=SplitParams(page_ranges=[(1, 2)], merge=True))
SPLIT_TO_ZIP = SplitOperation(
    operation="split", parameters=SplitParams(page_ranges=[(1, 1), (2, 2)], merge=False)
)
MERGE = MergeOperation(operation="merge", parameters={})
COMPRESS = CompressOperation(operation="compress", parameters=CompressParams(level=2))


class TestValidateOperationChain:
    """Page-based operations must never run against several files.

    The operations come from an LLM, so a chain like 'rotate page 3' on three
    uploads has to be refused in code, not quietly applied to the first file.
    """

    @pytest.mark.parametrize("operation", [ROTATE, SPLIT, SPLIT_TO_ZIP])
    def test_page_operation_on_several_files_is_rejected(self, operation):
        with pytest.raises(HTTPException) as exc_info:
            validate_operation_chain([operation], input_count=2)

        assert exc_info.value.status_code == 400
        assert "one PDF at a time" in exc_info.value.detail

    def test_page_operation_after_bulk_compress_is_rejected(self):
        """Compress keeps one output per file, so rotate would still be ambiguous."""
        with pytest.raises(HTTPException):
            validate_operation_chain([COMPRESS, ROTATE], input_count=3)

    @pytest.mark.parametrize(
        "chain",
        [
            [MERGE, ROTATE],
            [MERGE, SPLIT],
            [COMPRESS, MERGE, ROTATE, SPLIT_TO_ZIP],
        ],
    )
    def test_page_operation_after_merge_is_allowed(self, chain):
        validate_operation_chain(chain, input_count=3)

    def test_single_file_chain_is_allowed(self):
        validate_operation_chain([ROTATE, COMPRESS, SPLIT_TO_ZIP], input_count=1)

    def test_step_after_split_into_files_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_operation_chain([SPLIT_TO_ZIP, COMPRESS], input_count=1)

        assert "last step" in exc_info.value.detail

    def test_merge_of_a_single_file_is_rejected(self):
        with pytest.raises(HTTPException):
            validate_operation_chain([ROTATE, MERGE], input_count=1)

    def test_chain_runs_nothing_when_invalid(self, sample_pdf, tmp_path):
        with (
            patch("backend.services.operations_executor_service.rotate_pdf") as rotate,
            pytest.raises(HTTPException),
        ):
            execute_operation_chain([ROTATE], [sample_pdf, sample_pdf], tmp_path)

        rotate.assert_not_called()

    def test_execute_operation_refuses_to_pick_one_of_several_files(self, sample_pdf, tmp_output):
        with pytest.raises(HTTPException) as exc_info:
            execute_operation(ROTATE, [sample_pdf, sample_pdf], tmp_output)

        assert exc_info.value.status_code == 400


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
