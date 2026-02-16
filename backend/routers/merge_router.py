"""PDF merging router."""

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.services import merge_pdfs

router = APIRouter(prefix="/pdf/merge", tags=["pdf"])

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("")
async def merge_endpoint(files: list[UploadFile]) -> FileResponse:
    """Merge multiple uploaded PDF files into one."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="At least 2 PDF files required")

    for f in files:
        if f.content_type != "application/pdf":
            raise HTTPException(
                status_code=400, detail=f"File '{f.filename}' is not a PDF"
            )

    merge_id = uuid.uuid4().hex
    input_paths: list[Path] = []

    # Get first PDF's name without extension for the merged filename
    first_filename = files[0].filename or "document"
    first_name = Path(first_filename).stem
    output_filename = f"{first_name}_merged.pdf"
    output_path = UPLOAD_DIR / f"{merge_id}_{output_filename}"

    try:
        for i, f in enumerate(files):
            input_path = UPLOAD_DIR / f"{merge_id}_{i}.pdf"
            content = await f.read()
            input_path.write_bytes(content)
            input_paths.append(input_path)

        merge_pdfs(input_paths, output_path)

        return FileResponse(
            path=output_path,
            media_type="application/pdf",
            filename=output_filename,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}")
