"""Schemas for PDF splitting."""

from pydantic import BaseModel, Field, field_validator

from backend.validators.page_validators import validate_page_ranges


class SplitParams(BaseModel):
    """Validated parameters for PDF splitting."""

    page_ranges: list[tuple[int, int]] = Field(
        ...,
        description="List of (start, end) page ranges (1-indexed, inclusive). "
        "Example: [[1, 5], [7, 10]] means pages 1-5 and 7-10",
    )
    merge: bool = Field(
        True,
        description=(
            "If True, merge ranges into one PDF; "
            "if False, return ZIP of separate PDFs"
        ),
    )

    @field_validator("page_ranges")
    @classmethod
    def check_page_ranges(cls, v: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Validate page ranges using reusable validator."""
        return validate_page_ranges(v)
