"""PDF compression router."""

import json
import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.schemas import CompressParams
from backend.security import UPLOAD_DIR, cleanup_files, validate_and_save_pdf
from backend.services import compress_pdf

logger = logging.getLogger("nlpdf.compress")

router = APIRouter(prefix="/pdf/compress", tags=["pdf"])


@router.post("")
async def compress_endpoint(
    file: UploadFile,
    level: str = Form(...),
) -> FileResponse:
    """Compress an uploaded PDF file and return the compressed PDF."""
    try:
        params = CompressParams(level=json.loads(level))
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid compression level")

    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}.pdf"
    output_path = UPLOAD_DIR / f"{file_id}_compressed.pdf"

    try:
        await validate_and_save_pdf(file, input_path)

        compress_pdf(input_path, output_path, params.level)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"compressed_{file.filename}",
            background=BackgroundTask(cleanup_files, input_path, output_path),
        )
    except HTTPException:
        cleanup_files(input_path, output_path)
        raise
    except Exception:
        cleanup_files(input_path, output_path)
        logger.exception("Compression failed")
        raise HTTPException(status_code=500, detail="Compression failed")
