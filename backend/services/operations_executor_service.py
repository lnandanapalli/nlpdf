"""Execute validated LLM operations using existing services."""

from pathlib import Path
import zipfile

from fastapi import HTTPException, status
import structlog

from backend.schemas.llm_schema import (
    CompressOperation,
    MarkdownToPdfOperation,
    MergeOperation,
    OperationType,
    RotateOperation,
    SplitOperation,
)
from backend.services.compress_service import compress_pdf
from backend.services.markdown_service import markdown_to_pdf
from backend.services.merge_service import merge_pdfs
from backend.services.rotate_service import rotate_pdf
from backend.services.split_service import split_pdf

logger = structlog.get_logger(__name__)

# Operations that support bulk mode (apply to each file individually)
BULK_OPERATIONS = (CompressOperation, MarkdownToPdfOperation)
MIN_FILES_FOR_MERGE = 2
MAX_OPERATIONS_PER_CHAIN = 10
MAX_SPLIT_RANGES = 50


def execute_operation(
    operation: OperationType,
    input_paths: list[Path],
    output_path: Path,
    original_filename: str = "document",
) -> Path:
    """
    Execute a single validated operation.

    Returns:
        Path to the output file.

    Raises:
        HTTPException: If execution fails.
    """
    if isinstance(operation, MergeOperation) and len(input_paths) < MIN_FILES_FOR_MERGE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=("Merge requires multiple files. " f"Only {len(input_paths)} file(s) provided."),
        )

    def _invalid() -> None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This operation cannot be performed. " "Please describe a valid PDF operation."
            ),
        )

    if (
        isinstance(operation, SplitOperation)
        and len(operation.parameters.page_ranges) > MAX_SPLIT_RANGES
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many split ranges. Maximum {MAX_SPLIT_RANGES} allowed.",
        )

    try:
        if isinstance(operation, MergeOperation):
            for path in input_paths:
                if path.suffix.lower() != ".pdf":
                    _invalid()
            return merge_pdfs(input_paths, output_path)

        # For non-merge operations, execute on the first provided file
        main_input = input_paths[0]
        ext = main_input.suffix.lower()

        if isinstance(operation, CompressOperation):
            if ext != ".pdf":
                _invalid()
            return compress_pdf(main_input, output_path, operation.parameters.level)

        if isinstance(operation, SplitOperation):
            if ext != ".pdf":
                _invalid()
            params = operation.parameters
            if not params.merge:
                output_path = output_path.with_suffix(".zip")
            return split_pdf(
                main_input,
                params.page_ranges,
                params.merge,
                output_path,
                original_filename,
            )

        if isinstance(operation, RotateOperation):
            if ext != ".pdf":
                _invalid()
            return rotate_pdf(main_input, operation.parameters.rotations, output_path)

        if isinstance(operation, MarkdownToPdfOperation):
            if ext != ".md":
                _invalid()
            return markdown_to_pdf(main_input, output_path, operation.parameters.paper_size)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("Validation error in %s: %s", operation.operation, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The operation could not be completed. Please check "
            "that your page numbers and ranges are valid for the uploaded document.",
        ) from e
    except Exception:
        logger.exception("Operation %s failed", operation.operation)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong while processing your file. Please try again.",
        ) from None

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown operation")


def _is_bulk(operation: OperationType, input_count: int) -> bool:
    """Check if an operation should run in bulk mode."""
    return isinstance(operation, BULK_OPERATIONS) and input_count > 1


def _zip_results(
    result_paths: list[Path],
    output_dir: Path,
    original_filenames: list[str],
    op_name: str,
) -> Path:
    """ZIP multiple result files with meaningful names."""
    zip_path = output_dir / "output.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, path in enumerate(result_paths):
            name = original_filenames[i] if i < len(original_filenames) else f"file_{i + 1}"
            arc_name = f"{op_name}_{name}{path.suffix}"
            zf.write(path, arc_name)
    return zip_path


def execute_operation_chain(
    operations: list[OperationType],
    input_paths: list[Path],
    output_dir: Path,
    original_filename: str = "document",
    original_filenames: list[str] | None = None,
) -> Path:
    """
    Execute a chain of operations sequentially.

    Each operation's output becomes the next operation's input.
    Bulk-eligible operations (compress, markdown_to_pdf) are applied
    to each input file individually when multiple inputs exist.

    Args:
        operations: Ordered list of validated operations.
        input_paths: Initial input file paths.
        output_dir: Directory to write intermediate and final outputs.
        original_filename: Base name for the output file (single-file case).
        original_filenames: Per-file names for ZIP naming in bulk mode.

    Returns:
        Path to the final output file (or ZIP of results).

    Raises:
        HTTPException: If any operation fails or limits are exceeded.
    """
    if len(operations) > MAX_OPERATIONS_PER_CHAIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Instruction too complex. Maximum {MAX_OPERATIONS_PER_CHAIN} steps allowed.",
        )

    if original_filenames is None:
        original_filenames = [original_filename]

    # Single operation, single file — fast path (unchanged behavior)
    if len(operations) == 1 and not _is_bulk(operations[0], len(input_paths)):
        output_path = output_dir / "output.pdf"
        return execute_operation(operations[0], input_paths, output_path, original_filename)

    # Single bulk operation — no chain needed
    if len(operations) == 1 and _is_bulk(operations[0], len(input_paths)):
        results = _execute_bulk(operations[0], input_paths, output_dir)
        return _zip_results(results, output_dir, original_filenames, operations[0].operation)

    current_inputs = list(input_paths)
    result_path: Path | None = None
    intermediates: list[Path] = []

    for i, operation in enumerate(operations):
        is_last = i == len(operations) - 1

        if _is_bulk(operation, len(current_inputs)):
            step_dir = output_dir / f"step_{i}"
            step_dir.mkdir(exist_ok=True)
            results = _execute_bulk(operation, current_inputs, step_dir)
            intermediates.extend(results)

            if is_last:
                result_path = _zip_results(
                    results, output_dir, original_filenames, operation.operation
                )
            else:
                current_inputs = results
        else:
            if is_last:
                step_output = output_dir / "output.pdf"
            else:
                step_output = output_dir / f"step_{i}.pdf"
                intermediates.append(step_output)

            result_path = execute_operation(
                operation, current_inputs, step_output, original_filename
            )
            current_inputs = [result_path]

    # Clean up intermediate files
    for intermediate in intermediates:
        try:
            if intermediate.exists() and intermediate != result_path:
                intermediate.unlink()
        except OSError:
            pass

    if result_path is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No operations to execute"
        )
    return result_path


def _execute_bulk(
    operation: OperationType,
    input_paths: list[Path],
    output_dir: Path,
) -> list[Path]:
    """Apply an operation to each input file individually."""
    results: list[Path] = []
    for j, inp in enumerate(input_paths):
        sub_dir = output_dir / f"bulk_{j}"
        sub_dir.mkdir(exist_ok=True)
        sub_output = sub_dir / "output.pdf"
        result = execute_operation(operation, [inp], sub_output)
        results.append(result)
    return results
