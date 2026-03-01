"""Execute validated LLM operations using existing services."""

import structlog
from pathlib import Path

from fastapi import HTTPException

from backend.schemas.llm_schema import (
    CompressOperation,
    ExcelToPdfOperation,
    MarkdownToPdfOperation,
    MergeOperation,
    OperationType,
    PptxToPdfOperation,
    RotateOperation,
    SplitOperation,
    WordToPdfOperation,
)
from backend.services.compress_service import compress_pdf
from backend.services.excel_service import excel_to_pdf
from backend.services.markdown_service import markdown_to_pdf
from backend.services.merge_service import merge_pdfs
from backend.services.pptx_service import pptx_to_pdf
from backend.services.rotate_service import rotate_pdf
from backend.services.split_service import split_pdf
from backend.services.word_service import word_to_pdf

logger = structlog.get_logger(__name__)


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
    try:
        if isinstance(operation, MergeOperation):
            if len(input_paths) < 2:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Merge requires multiple files. "
                        f"Only {len(input_paths)} file(s) provided."
                    ),
                )
            return merge_pdfs(input_paths, output_path)

        # For non-merge operations, execute on the first provided file
        main_input = input_paths[0]

        if isinstance(operation, CompressOperation):
            return compress_pdf(main_input, output_path, operation.parameters.level)

        if isinstance(operation, SplitOperation):
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
            return rotate_pdf(main_input, operation.parameters.rotations, output_path)

        if isinstance(operation, MarkdownToPdfOperation):
            return markdown_to_pdf(
                main_input, output_path, operation.parameters.paper_size
            )

        if isinstance(operation, WordToPdfOperation):
            return word_to_pdf(main_input, output_path, operation.parameters.paper_size)

        if isinstance(operation, PptxToPdfOperation):
            return pptx_to_pdf(main_input, output_path, operation.parameters.paper_size)

        if isinstance(operation, ExcelToPdfOperation):
            return excel_to_pdf(
                main_input, output_path, operation.parameters.paper_size
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Operation %s failed", operation.operation)
        raise HTTPException(
            status_code=500,
            detail=f"PDF operation failed: {e}",
        )

    raise HTTPException(status_code=400, detail="Unknown operation")


def execute_operation_chain(
    operations: list[OperationType],
    input_paths: list[Path],
    output_dir: Path,
    original_filename: str = "document",
) -> Path:
    """
    Execute a chain of operations sequentially.

    Each operation's output becomes the next operation's input.

    Args:
        operations: Ordered list of validated operations.
        input_paths: Initial input file paths.
        output_dir: Directory to write intermediate and final outputs.
        original_filename: Base name for the output file.

    Returns:
        Path to the final output file.

    Raises:
        HTTPException: If any operation fails.
    """
    if len(operations) == 1:
        output_path = output_dir / "output.pdf"
        return execute_operation(
            operations[0], input_paths, output_path, original_filename
        )

    current_inputs = input_paths
    result_path: Path | None = None
    intermediates: list[Path] = []

    for i, operation in enumerate(operations):
        is_last = i == len(operations) - 1

        if is_last:
            step_output = output_dir / "output.pdf"
        else:
            step_output = output_dir / f"step_{i}.pdf"
            intermediates.append(step_output)

        result_path = execute_operation(
            operation, current_inputs, step_output, original_filename
        )

        # Next step takes this step's output as its single input
        current_inputs = [result_path]

    # Clean up intermediate files
    for intermediate in intermediates:
        try:
            if intermediate.exists() and intermediate != result_path:
                intermediate.unlink()
        except OSError:
            pass

    if result_path is None:
        raise HTTPException(status_code=400, detail="No operations to execute")
    return result_path
