"""Security utilities and middleware for the NLPDF API."""

import codecs
from pathlib import Path
import shutil
import tempfile
from typing import Any

import anyio
from anyio import to_thread
from fastapi import HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
import pikepdf
import structlog
from user_agents import parse as parse_ua

logger = structlog.get_logger(__name__)

# --- Constants ---
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_MARKDOWN_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per markdown file
MAX_TOTAL_UPLOAD_SIZE_BYTES = 150 * 1024 * 1024  # 150 MB total per request
MAX_MERGE_FILES = 50
PDF_MAGIC_BYTES = b"%PDF-"
ALLOWED_EXTENSIONS = frozenset({".pdf", ".md"})
UPLOAD_DIR = Path(tempfile.gettempdir()) / "nlpdf_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_pdf_sync(file_path: Path) -> None:
    """Synchronously sanitize a PDF using pikepdf to prevent polyglot attacks."""
    try:
        with pikepdf.open(file_path, allow_overwriting_input=True) as pdf:
            pdf.save(file_path)
    except pikepdf.PasswordError:
        raise ValueError(
            "This PDF is password-protected or encrypted. Please remove protection and try again."
        ) from None
    except pikepdf.PdfError as e:
        raise ValueError(f"Corrupted or invalid PDF structure: {e}") from e


async def validate_and_save_pdf(upload: UploadFile, dest: Path, current_total_size: int = 0) -> int:
    """
    Validate an uploaded file is a real PDF and save it to disk with size limits.

    Reads in chunks to avoid loading entire file into memory at once.
    Validates magic bytes from the first chunk.

    Args:
        upload: The uploaded file from FastAPI
        dest: Destination path to save the file
        current_total_size: Total bytes uploaded so far in this request

    Returns:
        Updated total bytes uploaded across all files

    Raises:
        HTTPException: If any size limit is exceeded, not a PDF, or empty
    """
    total_size = 0
    first_chunk = True
    chunk_size = 1024 * 1024  # 1 MB chunks
    error: HTTPException | None = None

    async with await anyio.open_file(dest, "wb") as f:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                break

            if first_chunk:
                if not chunk[:5].startswith(PDF_MAGIC_BYTES):
                    error = HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File '{upload.filename}' is not a valid PDF",
                    )
                    break
                first_chunk = False

            total_size += len(chunk)
            current_total_size += len(chunk)

            if total_size > MAX_FILE_SIZE_BYTES:
                error = HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File '{upload.filename}' exceeds maximum size "
                    f"of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB",
                )
                break

            if current_total_size > MAX_TOTAL_UPLOAD_SIZE_BYTES:
                limit_mb = MAX_TOTAL_UPLOAD_SIZE_BYTES // (1024 * 1024)
                error = HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Total upload size exceeds maximum allowed of {limit_mb} MB",
                )
                break

            await f.write(chunk)

    if error is not None:
        await anyio.Path(dest).unlink(missing_ok=True)
        raise error

    if total_size == 0:
        await anyio.Path(dest).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{upload.filename}' is empty",
        )

    try:
        await to_thread.run_sync(_sanitize_pdf_sync, dest)
    except ValueError as e:
        await anyio.Path(dest).unlink(missing_ok=True)
        logger.warning("pdf_sanitization_failed", filename=upload.filename, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file could not be verified as a valid PDF.",
        ) from e

    return current_total_size


async def validate_and_save_markdown(
    upload: UploadFile, dest: Path, current_total_size: int = 0
) -> int:
    """
    Validate an uploaded file is a valid markdown text file and save it.

    Reads in chunks to enforce size limits without loading the entire file.
    Uses an IncrementalDecoder to safely handle UTF-8 characters split across chunks.
    """
    total_size = 0
    chunk_size = 1024 * 1024  # 1 MB chunks
    error: HTTPException | None = None
    decoder = codecs.getincrementaldecoder("utf-8")()

    async with await anyio.open_file(dest, "wb") as f:
        while True:
            chunk = await upload.read(chunk_size)
            if not chunk:
                try:
                    decoder.decode(b"", final=True)
                except UnicodeDecodeError:
                    error = HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File '{upload.filename}' is not valid UTF-8 text",
                    )
                break

            total_size += len(chunk)
            current_total_size += len(chunk)

            if total_size > MAX_MARKDOWN_SIZE_BYTES:
                error = HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"File '{upload.filename}' exceeds maximum size "
                    f"of {MAX_MARKDOWN_SIZE_BYTES // (1024 * 1024)} MB",
                )
                break

            if current_total_size > MAX_TOTAL_UPLOAD_SIZE_BYTES:
                limit_mb = MAX_TOTAL_UPLOAD_SIZE_BYTES // (1024 * 1024)
                error = HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Total upload size exceeds maximum allowed of {limit_mb} MB",
                )
                break

            try:
                decoder.decode(chunk, final=False)
            except UnicodeDecodeError:
                error = HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File '{upload.filename}' is not valid UTF-8 text",
                )
                break

            await f.write(chunk)

    if error is not None:
        await anyio.Path(dest).unlink(missing_ok=True)
        raise error

    if total_size == 0:
        await anyio.Path(dest).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File '{upload.filename}' is empty",
        )

    return current_total_size


def cleanup_files(*paths: Path) -> None:
    """Delete temporary files or directories, ignoring errors."""
    for path in paths:
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to clean up temp path: %s", path)


class CleanupFileResponse(FileResponse):
    """A FileResponse that cleans up specified files/directories after the response is fully sent.

    This prevents the L5 race condition where files could be deleted before delivery completes.
    """

    def __init__(  # noqa: PLR0913
        self,
        path: str | Path,
        cleanup_paths: list[Path],
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        media_type: str | None = None,
        background: None = None,
        filename: str | None = None,
        stat_result: None = None,
        method: str | None = None,
        content_disposition_type: str = "attachment",
    ) -> None:
        """Initialize with a list of paths to delete after completion."""
        self.cleanup_paths = cleanup_paths
        super().__init__(
            path=path,
            status_code=status_code,
            headers=headers,
            media_type=media_type,
            background=background,
            filename=filename,
            stat_result=stat_result,
            method=method,
            content_disposition_type=content_disposition_type,
        )

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        """ASGI entry point for the response."""
        try:
            await super().__call__(scope, receive, send)
        finally:
            cleanup_files(*self.cleanup_paths)


def get_client_ip(request: Request) -> str:
    """Extract the real client IP from the request.

    X-Forwarded-For is built by each proxy APPENDING the IP it received
    the connection from. The client controls all entries it sends itself,
    but cannot remove or overwrite what a downstream trusted proxy appends.

      Client sends (may fake):   X-Forwarded-For: fake1, fake2
      1 trusted proxy appends:   X-Forwarded-For: fake1, fake2, real_ip
                                                                ↑
                                             [-1] = real client ✅

    Rule: use [-N] where N = number of trusted proxies in your chain.
      - 1 proxy between internet and app → [-1]
      - 2 proxies (e.g. CDN + app server) → [-2]
      - CDN with a dedicated verified-IP header → use that header instead
        (more reliable than index math)

    Current setup: 1 trusted proxy, so [-1] is the real client IP.
    Update this if you add a CDN or reverse proxy in front.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    # Direct connection fallback (e.g. local development with no proxy)
    return request.client.host if request.client else "unknown"


def parse_device_info(user_agent: str) -> dict:
    """Parse browser, OS, and device type from a User-Agent string.

    Uses the `user-agents` library (built on ua-parser) — handles thousands
    of devices, bots, and edge cases that manual regex cannot.

    Returns a dict with keys: device_name, browser, os, is_mobile.
    """
    ua = parse_ua(user_agent)

    # Device family: "iPhone", "Samsung SM-G991B", "Other" (desktop)
    device_family = ua.device.family
    if device_family == "Other":
        # Desktop — label by OS instead (e.g. "Windows 10/11", "macOS 14")
        os_ver = ua.os.version_string
        device_name = f"{ua.os.family} {os_ver}".strip() if os_ver else ua.os.family
    else:
        device_name = device_family

    # Browser: "Chrome 121", "Firefox 122", "Safari 17"
    browser_ver = ua.browser.version_string.split(".")[0]  # major version only
    browser = f"{ua.browser.family} {browser_ver}".strip() if browser_ver else ua.browser.family

    # OS: "iOS 17.2", "Android 14", "Windows 10/11"
    os_ver = ua.os.version_string
    os_name = f"{ua.os.family} {os_ver}".strip() if os_ver else ua.os.family

    is_mobile = 1 if (ua.is_mobile or ua.is_tablet) else 0

    return {
        "device_name": device_name[:200],
        "browser": browser[:100],
        "os": os_name[:100],
        "is_mobile": is_mobile,
    }
