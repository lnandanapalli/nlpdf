"""Security utilities and middleware for the NLPDF API."""

import structlog
import tempfile
from pathlib import Path

from fastapi import HTTPException, Request, UploadFile

logger = structlog.get_logger(__name__)

# --- Constants ---
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_MARKDOWN_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per markdown file
MAX_MERGE_FILES = 50
PDF_MAGIC_BYTES = b"%PDF-"
DOCX_MAGIC_BYTES = b"PK\x03\x04"
ALLOWED_EXTENSIONS = frozenset({".pdf", ".md", ".docx"})
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


async def validate_and_save_markdown(upload: UploadFile, dest: Path) -> None:
    """
    Validate an uploaded file is a valid markdown text file and save it.

    Reads in chunks to enforce size limits without loading the entire file.
    Validates that content is valid UTF-8 text.

    Args:
        upload: The uploaded file from FastAPI
        dest: Destination path to save the file

    Raises:
        HTTPException: If the file is too large, not valid UTF-8, or empty
    """
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB chunks
    error: HTTPException | None = None

    with open(dest, "wb") as f:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > MAX_MARKDOWN_SIZE_BYTES:
                error = HTTPException(
                    status_code=413,
                    detail=f"File '{upload.filename}' exceeds maximum size "
                    f"of {MAX_MARKDOWN_SIZE_BYTES // (1024 * 1024)} MB",
                )
                break

            try:
                chunk.decode("utf-8")
            except UnicodeDecodeError:
                error = HTTPException(
                    status_code=400,
                    detail=f"File '{upload.filename}' is not valid UTF-8 text",
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


async def validate_and_save_docx(upload: UploadFile, dest: Path) -> None:
    """
    Validate an uploaded file is a real DOCX and save it to disk with size limits.

    DOCX files are ZIP archives, so we check for the ZIP magic bytes (PK\\x03\\x04).
    Reads in chunks to avoid loading entire file into memory at once.

    Args:
        upload: The uploaded file from FastAPI
        dest: Destination path to save the file

    Raises:
        HTTPException: If the file is too large, not a DOCX, or empty
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
                if not chunk[:4].startswith(DOCX_MAGIC_BYTES):
                    error = HTTPException(
                        status_code=400,
                        detail=f"File '{upload.filename}' is not a valid DOCX",
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
    """Delete temporary files or directories, ignoring errors."""
    import shutil

    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to clean up temp path: %s", path)


def get_client_ip(request: Request) -> str:
    """Extract client IP for rate limiting."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
