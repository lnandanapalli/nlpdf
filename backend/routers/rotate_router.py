"""PDF rotation router."""

import json
import logging
import uuid

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from starlette.background import BackgroundTask

from backend.schemas.rotate_schema import RotateParams
from backend.security import UPLOAD_DIR, cleanup_files, validate_and_save_pdf
from backend.services.rotate_service import rotate_pdf

logger = logging.getLogger("nlpdf.rotate")

router = APIRouter(prefix="/pdf/rotate", tags=["pdf"])


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
        await validate_and_save_pdf(file, input_path)

        rotate_pdf(input_path, params.rotations, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=f"rotated_{file.filename}",
            background=BackgroundTask(cleanup_files, input_path, output_path),
        )
    except HTTPException:
        cleanup_files(input_path, output_path)
        raise
    except Exception:
        cleanup_files(input_path, output_path)
        logger.exception("Rotation failed")
        raise HTTPException(status_code=500, detail="Rotation failed")
