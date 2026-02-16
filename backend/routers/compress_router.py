"""PDF compression router."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.schemas import CompressParams
from backend.services import compress_pdf

router = APIRouter(prefix="/pdf/compress", tags=["pdf"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("")
async def compress_endpoint(
    file: UploadFile,
    level: str = Form(...),
) -> FileResponse:
    """Compress an uploaded PDF file and return the compressed PDF."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        params = CompressParams(level=json.loads(level))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid params: {e}")

    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}.pdf"
    output_path = UPLOAD_DIR / f"{file_id}_compressed.pdf"

    try:
        content = await file.read()
        input_path.write_bytes(content)

        compress_pdf(input_path, output_path, params.level)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"compressed_{file.filename}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Compression failed: {e}",
        )
