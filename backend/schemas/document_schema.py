"""Schemas for the document history API."""

from datetime import datetime

from pydantic import BaseModel

# Page size bounds for GET /documents.
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class DocumentResponse(BaseModel):
    """A single processed document, as shown in the history list."""

    id: int
    original_filename: str
    operation_type: str
    input_size_mb: str | None = None
    output_size_mb: str | None = None
    page_count: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """One page of document history, plus the total for pagination."""

    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentsClearedResponse(BaseModel):
    """Result of clearing history."""

    message: str
    deleted: int
