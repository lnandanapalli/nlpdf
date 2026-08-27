"""CRUD operations for PDF documents."""

from typing import cast

from sqlalchemy import CursorResult, delete, func, select
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
    await db.flush()  # Needed to populate db_document.id before the transaction commits
    return db_document


async def get_documents_for_user(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    """Return one page of a user's documents, newest first."""
    result = await db.execute(
        select(Document)
        .where(Document.owner_id == user_id)
        .order_by(Document.created_at.desc(), Document.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def count_documents_for_user(db: AsyncSession, user_id: int) -> int:
    """Return how many documents a user owns."""
    result = await db.execute(
        select(func.count()).select_from(Document).where(Document.owner_id == user_id)
    )
    return int(result.scalar_one())


async def delete_document_by_id(db: AsyncSession, document_id: int, user_id: int) -> bool:
    """Delete one document by primary key, scoped to the owning user.

    Returns True when a row was removed. A missing document and a document owned
    by somebody else are deliberately indistinguishable, so the result cannot be
    used to probe for other users' document ids.
    """
    result = cast(
        "CursorResult",
        await db.execute(
            delete(Document).where(
                Document.id == document_id,
                Document.owner_id == user_id,
            )
        ),
    )
    return bool(result.rowcount)


async def delete_all_documents_for_user(db: AsyncSession, user_id: int) -> int:
    """Delete every document a user owns. Returns the number removed."""
    result = cast(
        "CursorResult",
        await db.execute(delete(Document).where(Document.owner_id == user_id)),
    )
    return int(result.rowcount or 0)
