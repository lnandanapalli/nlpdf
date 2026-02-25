"""CRUD operations for PDF documents."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.document import Document


async def create_document(
    db: AsyncSession,
    owner_id: int,
    original_filename: str,
    operation_type: str,
    input_size_mb: str | None = None,
    output_size_mb: str | None = None,
    page_count: int | None = None,
) -> Document:
    """Create a new document record in the database."""
    db_document = Document(
        owner_id=owner_id,
        original_filename=original_filename,
        operation_type=operation_type,
        input_size_mb=input_size_mb,
        output_size_mb=output_size_mb,
        page_count=page_count,
    )
    db.add(db_document)
    await db.commit()
    await db.refresh(db_document)
    return db_document
