"""JSON protocol schemas for LLM-generated operations."""

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from backend.schemas.compress_schema import CompressParams
from backend.schemas.markdown_schema import MarkdownToPdfParams
from backend.schemas.rotate_schema import RotateParams
from backend.schemas.split_schema import SplitParams


class CompressOperation(BaseModel):
    """Compress operation from LLM."""

    operation: Literal["compress"]
    parameters: CompressParams


class SplitOperation(BaseModel):
    """Split operation from LLM."""

    operation: Literal["split"]
    parameters: SplitParams


class RotateOperation(BaseModel):
    """Rotate operation from LLM."""

    operation: Literal["rotate"]
    parameters: RotateParams


class MergeOperation(BaseModel):
    """Merge operation from LLM (no parameters)."""

    operation: Literal["merge"]
    parameters: dict = Field(default_factory=dict)


class MarkdownToPdfOperation(BaseModel):
    """Markdown to PDF conversion operation from LLM."""

    operation: Literal["markdown_to_pdf"]
    parameters: MarkdownToPdfParams = Field(default_factory=MarkdownToPdfParams)


# All allowed operation types
OperationType = (
    CompressOperation
    | SplitOperation
    | RotateOperation
    | MergeOperation
    | MarkdownToPdfOperation
)

# Maps operation name -> typed model
OPERATION_MAP: dict[str, type[BaseModel]] = {
    "compress": CompressOperation,
    "split": SplitOperation,
    "rotate": RotateOperation,
    "merge": MergeOperation,
    "markdown_to_pdf": MarkdownToPdfOperation,
}

ALLOWED_OPERATIONS = frozenset(OPERATION_MAP.keys())


def validate_llm_json(
    llm_output: dict[str, Any],
) -> OperationType:
    """
    Validate LLM-generated JSON against allowed operations.

    Two-phase validation:
    1. Check operation name is one of the allowed set
    2. Validate parameters against the operation-specific schema

    Returns the fully-typed operation model.

    Raises:
        ValueError: If operation is unknown or parameters are invalid
    """
    operation = llm_output.get("operation")
    if operation not in ALLOWED_OPERATIONS:
        raise ValueError(
            f"Unknown operation '{operation}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_OPERATIONS))}"
        )

    model_class = OPERATION_MAP[operation]
    try:
        return model_class(**llm_output)  # type: ignore[return-value]
    except ValidationError as e:
        raise ValueError(f"Invalid parameters for '{operation}': {e}") from e


def validate_llm_json_list(
    llm_output: list[dict[str, Any]],
) -> list[OperationType]:
    """
    Validate a list of LLM-generated operations.

    Returns:
        List of fully-typed operation models.

    Raises:
        ValueError: If any operation is invalid.
    """
    if not llm_output:
        raise ValueError("Empty operations list")

    operations: list[OperationType] = []
    for i, item in enumerate(llm_output):
        try:
            operations.append(validate_llm_json(item))
        except ValueError as e:
            raise ValueError(f"Operation {i + 1}: {e}") from e

    return operations
