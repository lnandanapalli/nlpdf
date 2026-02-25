"""PDF splitting router."""

import json
import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from backend.schemas.split_schema import SplitParams
from backend.security import UPLOAD_DIR, cleanup_files, validate_and_save_pdf
from backend.services.split_service import split_pdf

logger = logging.getLogger("nlpdf.split")

router = APIRouter(prefix="/pdf/split", tags=["pdf"])


@router.post("")
async def split_endpoint(
    file: UploadFile,
    page_ranges: str = Form(
        ...,
        description="JSON list of [start, end] pairs (1-indexed, inclusive). "
        "Example: [[1, 5], [7, 10]] = pages 1-5 and 7-10",
    ),
    merge: bool = Form(
        True,
        description="If True, merge ranges into one PDF; if False, return ZIP of "
        "separate PDFs",
    ),
) -> FileResponse:
    """Split a PDF by extracting specific page ranges."""
    try:
        raw = json.loads(page_ranges)
        params = SplitParams(page_ranges=raw, merge=merge)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}.pdf"

    # Determine output extension based on merge parameter
    if merge:
        output_path = UPLOAD_DIR / f"{file_id}_split.pdf"
        media_type = "application/pdf"
        filename = f"split_{file.filename or 'document'}"
    else:
        output_path = UPLOAD_DIR / f"{file_id}_split.zip"
        media_type = "application/zip"
        base_name = (file.filename or "document").rsplit(".", 1)[0]
        filename = f"split_{base_name}.zip"

    try:
        await validate_and_save_pdf(file, input_path)

        # Extract original filename without extension
        original_name = (file.filename or "document").rsplit(".", 1)[0]

        split_pdf(
            input_path, params.page_ranges, params.merge, output_path, original_name
        )

        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=filename,
            background=BackgroundTask(cleanup_files, input_path, output_path),
        )
    except HTTPException:
        cleanup_files(input_path, output_path)
        raise
    except Exception:
        cleanup_files(input_path, output_path)
        logger.exception("Split failed")
        raise HTTPException(status_code=500, detail="Split failed")
