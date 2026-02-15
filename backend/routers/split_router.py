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
        ..., description="JSON list of [start, end] pairs, e.g. [[0, 3], [5, 8]]"
    ),
) -> FileResponse:
    """Split a PDF by extracting specific page ranges."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        raw = json.loads(page_ranges)
        params = SplitParams(page_ranges=raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}.pdf"
    output_path = UPLOAD_DIR / f"{file_id}_split.pdf"

    try:
        content = await file.read()
        input_path.write_bytes(content)

        split_pdf(input_path, params.page_ranges, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"split_{file.filename}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Split failed: {e}")
