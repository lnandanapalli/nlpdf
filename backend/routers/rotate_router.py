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
    rotations: str = Form(
        ...,
        description="JSON list of [page_num, angle] tuples (1-indexed, clockwise). "
        "Example: [[1, 90], [3, 180], [5, 270]] - angles: 90, 180, or 270",
    ),
) -> FileResponse:
    """Rotate pages in an uploaded PDF file with individual rotation settings."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        parsed_rotations = json.loads(rotations)
        params = RotateParams(rotations=parsed_rotations)
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

        rotate_pdf(input_path, params.rotations, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"rotated_{file.filename}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rotation failed: {e}")
