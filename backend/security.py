"""Security utilities and middleware for the NLPDF API."""

import logging
import tempfile
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile

logger = logging.getLogger("nlpdf.security")

# --- Constants ---
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_MERGE_FILES = 50
PDF_MAGIC_BYTES = b"%PDF-"
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nlpdf_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def validate_and_save_pdf(upload: UploadFile, dest: Path) -> None:
    """
    Validate an uploaded file is a real PDF and save it to disk with size limits.

    Reads in chunks to avoid loading entire file into memory at once.
    Validates magic bytes from the first chunk.

    Args:
        upload: The uploaded file from FastAPI
        dest: Destination path to save the file

    Raises:
        HTTPException: If the file is too large, not a PDF, or empty
    """
    total_size = 0
    first_chunk = True
    chunk_size = 1024 * 1024  # 1 MB chunks
    error: HTTPException | None = None

    with open(dest, "wb") as f:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break

            if first_chunk:
                if not chunk[:5].startswith(PDF_MAGIC_BYTES):
                    error = HTTPException(
                        status_code=400,
                        detail=f"File '{upload.filename}' is not a valid PDF",
                    )
                    break
                first_chunk = False

            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE_BYTES:
                error = HTTPException(
                    status_code=413,
                    detail=f"File '{upload.filename}' exceeds maximum size "
                    f"of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
                )
                break

            f.write(chunk)

    if error is not None:
        dest.unlink(missing_ok=True)
        raise error

    if total_size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail=f"File '{upload.filename}' is empty",
        )


def cleanup_files(*paths: Path) -> None:
    """Delete temporary files, ignoring errors for already-deleted files."""
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to clean up temp file: %s", path)


def get_client_ip(request: Request) -> str:
    """Extract client IP for rate limiting."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
