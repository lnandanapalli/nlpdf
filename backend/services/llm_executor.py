"""Execute validated LLM operations using existing services."""

import logging
from pathlib import Path

from fastapi import HTTPException

from backend.schemas.llm_schema import (
    CompressOperation,
    MergeOperation,
    OperationType,
    RotateOperation,
    SplitOperation,
)
from backend.services.compress_service import compress_pdf
from backend.services.merge_service import merge_pdfs
from backend.services.rotate_service import rotate_pdf
from backend.services.split_service import split_pdf

logger = logging.getLogger("nlpdf.llm_executor")


def execute_operation(
    operation: OperationType,
    input_paths: list[Path],
    output_path: Path,
    original_filename: str = "document",
) -> Path:
    """
    Execute a validated operation using existing services.

    Parameters are already validated by the schema layer - no need
    to re-validate here.

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

        # For non-merge operations, we just execute on the first provided file
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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Operation %s failed", operation.operation)
        raise HTTPException(
            status_code=500,
            detail=f"PDF operation failed: {e}",
        )

    # Unreachable, but satisfies type checker
    raise HTTPException(status_code=400, detail="Unknown operation")
