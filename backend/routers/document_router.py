"""Document history endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from backend.auth.dependencies import get_current_user
from backend.crud.document_crud import (
    count_documents_for_user,
    delete_all_documents_for_user,
    delete_document_by_id,
    get_documents_for_user,
)
from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth_schema import SuccessResponse
from backend.schemas.document_schema import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    DocumentListResponse,
    DocumentResponse,
    DocumentsClearedResponse,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("")
async def list_documents(
    current_user: CurrentUser,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """Return the caller's processed-document history, newest first."""
    documents = await get_documents_for_user(db, current_user.id, limit=limit, offset=offset)
    total = await count_documents_for_user(db, current_user.id)
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    current_user: CurrentUser,
    db: DB,
) -> SuccessResponse:
    """Delete one document from the caller's history."""
    deleted = await delete_document_by_id(db, document_id, current_user.id)
    if not deleted:
        # Same response whether it never existed or belongs to somebody else,
        # so this cannot be used to enumerate other users' document ids.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    logger.info("document_deleted", user_id=current_user.id, document_id=document_id)
    return SuccessResponse(message="Document deleted")


@router.delete("")
async def clear_documents(
    current_user: CurrentUser,
    db: DB,
) -> DocumentsClearedResponse:
    """Delete the caller's entire document history."""
    deleted = await delete_all_documents_for_user(db, current_user.id)
    logger.info("documents_cleared", user_id=current_user.id, deleted=deleted)
    return DocumentsClearedResponse(message="History cleared", deleted=deleted)
