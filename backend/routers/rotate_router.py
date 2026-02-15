"""PDF rotation router."""

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError

from backend.schemas import RotateParams
from backend.services import rotate_pdf

router = APIRouter(prefix="/pdf/rotate", tags=["pdf"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("")
async def rotate_endpoint(
    file: UploadFile,
    rotation: int = Form(..., description="Rotation angle (90, 180, 270)"),
    page_indices: str | None = Form(
        None, description="JSON list of page indices, e.g. [0, 2, 4]. Omit for all."
    ),
) -> FileResponse:
    """Rotate pages in an uploaded PDF file."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        parsed_indices = json.loads(page_indices) if page_indices else None
        params = RotateParams(rotation=rotation, page_indices=parsed_indices)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}.pdf"
    output_path = UPLOAD_DIR / f"{file_id}_rotated.pdf"

    try:
        content = await file.read()
        input_path.write_bytes(content)

        rotate_pdf(input_path, params.rotation, params.page_indices, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"rotated_{file.filename}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rotation failed: {e}")
