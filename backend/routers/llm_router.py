"""LLM-powered natural language PDF processing endpoint."""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pypdf import PdfReader
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from backend.security import UPLOAD_DIR, cleanup_files, validate_and_save_pdf
from backend.services.llm_service import LLMService, get_llm_service
from backend.services.operations_executor_service import execute_operation

logger = logging.getLogger("nlpdf.llm")

router = APIRouter(prefix="/pdf", tags=["pdf"])


@router.post("/process")
async def process_with_llm(
    files: list[UploadFile],
    message: str = Form(
        ...,
        description=(
            "Natural language instruction for PDF processing. "
            "Examples: 'compress this', 'extract first 10 pages', "
            "'merge these files'"
        ),
    ),
    llm_service: LLMService = Depends(get_llm_service),
) -> FileResponse:
    """
    Process a PDF using natural language instructions.

    The LLM interprets the message and executes the appropriate
    operation: compress, split, or rotate.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    file_id = uuid.uuid4().hex
    output_path = UPLOAD_DIR / f"{file_id}_out.pdf"

    input_paths = []
    temps = [output_path]
    for i, file in enumerate(files):
        in_path = UPLOAD_DIR / f"{file_id}_{i}.pdf"
        input_paths.append(in_path)
        temps.append(in_path)

    try:
        # 1. Validate and save uploaded PDFs
        for file, in_path in zip(files, input_paths):
            await validate_and_save_pdf(file, in_path)

        # 2. Extract PDF metadata for LLM context
        pdf_metadata_list = []
        for in_path in input_paths:
            metadata = await run_in_threadpool(_extract_metadata, in_path)
            if metadata:
                pdf_metadata_list.append(metadata)

        total_pages = sum(m["page_count"] for m in pdf_metadata_list)
        total_size = round(sum(m["file_size_mb"] for m in pdf_metadata_list), 2)
        combined_metadata = {
            "file_count": len(files),
            "total_page_count": total_pages,
            "total_file_size_mb": total_size,
        }

        # 3. LLM: parse message -> validate -> typed operation
        operation = await llm_service.process_message(
            user_message=message,
            pdf_metadata=combined_metadata,
        )

        # 4. Execute the operation
        original_name = (files[0].filename or "document").rsplit(".", 1)[0]
        if len(files) > 1:
            original_name = "merged_documents"

        result_path = await run_in_threadpool(
            execute_operation,
            operation,
            input_paths,
            output_path,
            original_name,
        )

        # Update temps in case executor changed the output path (.zip)
        if result_path != output_path:
            temps.append(result_path)

        # 5. Determine response type
        if result_path.suffix == ".zip":
            media_type = "application/zip"
            filename = f"{original_name}_split.zip"
        else:
            media_type = "application/pdf"
            filename = f"{operation.operation}_{original_name}.pdf"

        return FileResponse(
            path=result_path,
            media_type=media_type,
            filename=filename,
            background=BackgroundTask(cleanup_files, *temps),
        )

    except HTTPException:
        cleanup_files(*temps)
        raise
    except Exception as e:
        cleanup_files(*temps)
        logger.exception("Processing failed")
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")


def _extract_metadata(input_path: Path) -> dict | None:
    """Extract page count and file size. Returns None on failure."""
    try:
        reader = PdfReader(input_path)
        return {
            "page_count": len(reader.pages),
            "file_size_mb": round(input_path.stat().st_size / (1024 * 1024), 2),
        }
    except Exception as e:
        logger.warning("Could not read PDF metadata: %s", e)
        return None
