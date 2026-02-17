"""PDF merging router."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.security import (
    MAX_MERGE_FILES,
    UPLOAD_DIR,
    cleanup_files,
    validate_and_save_pdf,
)
from backend.services import merge_pdfs

logger = logging.getLogger("nlpdf.merge")

router = APIRouter(prefix="/pdf/merge", tags=["pdf"])


@router.post("")
async def merge_endpoint(files: list[UploadFile]) -> FileResponse:
    """Merge multiple uploaded PDF files into one."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 PDF files required")

    if len(files) > MAX_MERGE_FILES:
        raise HTTPException(
            status_code=400, detail=f"Maximum {MAX_MERGE_FILES} files allowed per merge"
        )

    merge_id = uuid.uuid4().hex
    input_paths = []

    # Get first PDF's name without extension for the merged filename
    first_filename = files[0].filename or "document"
    first_name = first_filename.rsplit(".", 1)[0]
    output_filename = f"{first_name}_merged.pdf"
    output_path = UPLOAD_DIR / f"{merge_id}_{output_filename}"

    try:
        for i, f in enumerate(files):
            input_path = UPLOAD_DIR / f"{merge_id}_{i}.pdf"
            await validate_and_save_pdf(f, input_path)
            input_paths.append(input_path)

        merge_pdfs(input_paths, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=output_filename,
            background=BackgroundTask(cleanup_files, *input_paths, output_path),
        )
    except HTTPException:
        cleanup_files(*input_paths, output_path)
        raise
    except Exception:
        cleanup_files(*input_paths, output_path)
        logger.exception("Merge failed")
        raise HTTPException(status_code=500, detail="Merge failed")
