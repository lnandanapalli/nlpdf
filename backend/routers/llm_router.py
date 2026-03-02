"""LLM-powered natural language PDF processing endpoint."""

import structlog
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pypdf import PdfReader
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.crud.document_crud import create_document
from backend.database import get_db
from backend.models.user import User
from backend.security import (
    ALLOWED_EXTENSIONS,
    MAX_MERGE_FILES,
    UPLOAD_DIR,
    cleanup_files,
    validate_and_save_markdown,
    validate_and_save_pdf,
)
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.operations_executor_service import execute_operation_chain

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/pdf", tags=["pdf"])


def _get_file_ext(filename: str | None) -> str:
    """Extract lowercase file extension from a filename."""
    if not filename:
        return ""
    return Path(filename).suffix.lower()


@router.post("/process")
async def process_with_llm(
    files: list[UploadFile],
    message: str = Form(
        ...,
        description=(
            "Natural language instruction for PDF processing. "
            "Examples: 'compress this', 'extract first 10 pages', "
            "'merge these files', 'convert to PDF'"
        ),
    ),
    llm_service: LLMService = Depends(get_llm_service),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Process PDF(s) or markdown file(s) using natural language instructions.

    Supports chained operations (e.g. "merge then compress").
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > MAX_MERGE_FILES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many files: {len(files)} provided, "
                f"maximum is {MAX_MERGE_FILES}"
            ),
        )

    # Determine file types and reject unsupported or mixed uploads
    extensions = {_get_file_ext(f.filename) for f in files}
    unsupported = extensions - ALLOWED_EXTENSIONS
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type(s): {', '.join(sorted(unsupported))}. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    if len(extensions) > 1:
        raise HTTPException(
            status_code=400,
            detail="Mixed file types are not supported. "
            "Upload all files of the same type.",
        )

    file_type = extensions.pop()
    is_markdown = file_type == ".md"

    file_id = uuid.uuid4().hex
    output_dir = UPLOAD_DIR / file_id
    output_dir.mkdir(parents=True, exist_ok=True)

    input_paths = []
    temps: list[Path] = [output_dir]
    for i, file in enumerate(files):
        in_path = UPLOAD_DIR / f"{file_id}_{i}{file_type}"
        input_paths.append(in_path)
        temps.append(in_path)

    try:
        # 1. Validate and save uploaded files
        for file, in_path in zip(files, input_paths):
            if is_markdown:
                await validate_and_save_markdown(file, in_path)
            else:
                await validate_and_save_pdf(file, in_path)

        # 2. Extract metadata for LLM context
        total_pages = 0
        total_size = 0.0

        if is_markdown:
            for in_path in input_paths:
                total_size += round(in_path.stat().st_size / (1024 * 1024), 2)
        else:
            pdf_metadata_list = []
            for in_path in input_paths:
                metadata = await run_in_threadpool(_extract_metadata, in_path)
                if metadata:
                    pdf_metadata_list.append(metadata)
            total_pages = sum(m["page_count"] for m in pdf_metadata_list)
            total_size = round(sum(m["file_size_mb"] for m in pdf_metadata_list), 2)

        combined_metadata = {
            "file_count": len(files),
            "file_type": file_type,
            "total_page_count": total_pages,
            "total_file_size_mb": total_size,
        }

        # 3. LLM: parse message -> validate -> typed operations
        operations = await llm_service.process_message(
            user_message=message,
            pdf_metadata=combined_metadata,
        )

        # 4. Execute the operation chain
        original_name = Path(files[0].filename or "document").stem
        if len(files) > 1:
            original_name = "merged_documents"

        result_path = await run_in_threadpool(
            execute_operation_chain,
            operations,
            input_paths,
            output_dir,
            original_name,
        )

        if result_path.suffix == ".zip":
            media_type = "application/zip"
            filename = f"{original_name}_split.zip"
        else:
            media_type = "application/pdf"
            last_op = operations[-1].operation
            filename = f"{last_op}_{original_name}.pdf"

        # 5. Save document record to database
        out_size_mb = str(round(result_path.stat().st_size / (1024 * 1024), 2))
        op_type = ",".join(op.operation for op in operations)

        await create_document(
            db=db,
            owner_id=int(current_user.id),  # type: ignore
            original_filename=original_name,
            operation_type=op_type,
            input_size_mb=str(total_size),
            output_size_mb=out_size_mb,
            page_count=total_pages,
        )

        return FileResponse(
            path=result_path,
            media_type=media_type,
            filename=filename,
            background=BackgroundTask(cleanup_files, *temps),
        )

    except HTTPException:
        cleanup_files(*temps)
        raise
    except Exception:
        cleanup_files(*temps)
        logger.exception("Processing failed")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your "
            "request. Please try again.",
        )


def _extract_metadata(input_path: Path) -> dict | None:
    """Extract page count and file size. Returns None on failure."""
    try:
        reader = PdfReader(input_path)
        return {
            "page_count": len(reader.pages),
            "file_size_mb": round(input_path.stat().st_size / (1024 * 1024), 2),
        }
    except Exception as e:
        logger.warning("Could not read PDF metadata: %s", e)
        return None
