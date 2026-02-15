"""PDF splitting router."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from backend.schemas import SplitParams
from backend.services import split_pdf

router = APIRouter(prefix="/pdf/split", tags=["pdf"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

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
        content = await file.read()
        input_path.write_bytes(content)

        # Extract original filename without extension
        original_name = (file.filename or "document").rsplit(".", 1)[0]

        split_pdf(
            input_path, params.page_ranges, params.merge, output_path, original_name
        )

        return FileResponse(
            path=output_path,
            media_type=media_type,
            filename=filename,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Split failed: {e}")
