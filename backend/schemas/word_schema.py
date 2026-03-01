"""Schemas for Word to PDF conversion."""

from typing import Literal

from pydantic import BaseModel, Field


class WordToPdfParams(BaseModel):
    """Validated parameters for Word to PDF conversion."""

    paper_size: Literal["A4", "letter"] = Field(
        default="A4",
        description="Paper size for the output PDF: A4 or letter",
    )
