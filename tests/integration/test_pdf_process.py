"""POST /pdf/process through the full app: upload -> LLM plan -> pipeline -> response."""

import io
from pathlib import Path
from unittest.mock import patch
import zipfile

from fastapi import HTTPException
from pypdf import PdfReader
import pytest
from sqlalchemy import select

from backend.models.document import Document
from backend.security import MAX_MERGE_FILES, UPLOAD_DIR
from tests.integration.conftest import SessionLocal
from tests.integration.conftest import make_pdf as pdf


def files(*items: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, data, "application/octet-stream")) for name, data in items]


async def process(client, uploads, message="do it"):
    return await client.post("/pdf/process", files=uploads, data={"message": message})


async def documents() -> list[Document]:
    async with SessionLocal() as db:
        return list((await db.execute(select(Document))).scalars().all())


@pytest.fixture
def upload_dir_snapshot():
    """Entries in the upload dir before the test; anything new afterwards leaked."""
    before = set(UPLOAD_DIR.iterdir())
    yield before
    leaked = set(UPLOAD_DIR.iterdir()) - before
    assert not leaked, f"temp files left behind: {sorted(p.name for p in leaked)}"


class TestAccessControl:
    async def test_requires_login(self, anon, llm):
        resp = await process(anon, files(("a.pdf", pdf(1))))
        assert resp.status_code in (401, 403)
        assert not llm.calls

    async def test_requires_csrf_header(self, user, llm):
        del user.headers["X-CSRF-Token"]
        resp = await process(user, files(("a.pdf", pdf(1))))
        assert resp.status_code == 403
        assert not llm.calls


@pytest.mark.usefixtures("upload_dir_snapshot")
class TestSuccessfulOperations:
    async def test_compress_returns_a_pdf_and_records_history(self, user, llm):
        llm.plan = [{"operation": "compress", "parameters": {"level": 2}}]

        resp = await process(user, files(("report.pdf", pdf(3))), "compress this")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert 'filename="compress_report.pdf"' in resp.headers["content-disposition"]
        assert len(PdfReader(io.BytesIO(resp.content)).pages) == 3

        # The LLM saw the request and the file facts it needs to plan.
        assert llm.calls[0]["message"] == "compress this"
        assert llm.calls[0]["metadata"]["total_page_count"] == 3

        [doc] = await documents()
        assert (doc.original_filename, doc.operation_type, doc.page_count) == (
            "report",
            "compress",
            3,
        )

    async def test_split_into_separate_files_returns_a_zip(self, user, llm):
        llm.plan = [
            {"operation": "split", "parameters": {"page_ranges": [[1, 2], [3, 4]], "merge": False}}
        ]

        resp = await process(user, files(("book.pdf", pdf(4))))

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert 'filename="split_book.zip"' in resp.headers["content-disposition"]
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            parts = [len(PdfReader(io.BytesIO(zf.read(n))).pages) for n in sorted(zf.namelist())]
        assert parts == [2, 2]

    async def test_merge_then_rotate(self, user, llm):
        llm.plan = [
            {"operation": "merge", "parameters": {}},
            {"operation": "rotate", "parameters": {"rotations": [[2, 90]]}},
        ]

        resp = await process(user, files(("a.pdf", pdf(1)), ("b.pdf", pdf(2))))

        assert resp.status_code == 200
        reader = PdfReader(io.BytesIO(resp.content))
        assert [p.rotation for p in reader.pages] == [0, 90, 0]
        [doc] = await documents()
        assert doc.operation_type == "merge,rotate"
        assert doc.original_filename == "documents"

    async def test_markdown_to_pdf(self, user, llm):
        llm.plan = [{"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}}]

        resp = await process(user, files(("notes.md", b"# Title\n\nSome *text*.\n")))

        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF")

    async def test_hostile_filename_cannot_reach_the_header(self, user, llm):
        resp = await process(user, files(('../../etc/pa"ss\r\nX-Evil: 1.pdf', pdf(1))))

        assert resp.status_code == 200
        disposition = resp.headers["content-disposition"]
        assert ".." not in disposition
        assert "/" not in disposition
        assert "x-evil" not in {k.lower() for k in resp.headers}


@pytest.mark.usefixtures("upload_dir_snapshot")
class TestRejectedRequests:
    async def _expect_400(self, user, llm, uploads, detail_part):
        resp = await process(user, uploads)
        assert resp.status_code == 400, resp.text
        assert detail_part in resp.json()["detail"]
        assert await documents() == []

    async def test_rotate_on_several_files_is_refused(self, user, llm):
        llm.plan = [{"operation": "rotate", "parameters": {"rotations": [[1, 90]]}}]
        await self._expect_400(
            user, llm, files(("a.pdf", pdf(2)), ("b.pdf", pdf(2))), "one PDF at a time"
        )

    async def test_unsupported_type(self, user, llm):
        await self._expect_400(user, llm, files(("a.txt", b"hello")), "Unsupported file type")
        assert not llm.calls

    async def test_mixed_types(self, user, llm):
        await self._expect_400(
            user, llm, files(("a.pdf", pdf(1)), ("b.md", b"# x")), "Mixed file types"
        )

    async def test_too_many_files(self, user, llm):
        uploads = files(*[(f"f{i}.pdf", pdf(1)) for i in range(MAX_MERGE_FILES + 1)])
        await self._expect_400(user, llm, uploads, "Too many files")

    async def test_bytes_that_are_not_a_pdf(self, user, llm):
        await self._expect_400(user, llm, files(("fake.pdf", b"MZ not a pdf")), "not a valid PDF")
        assert not llm.calls

    async def test_empty_file(self, user, llm):
        await self._expect_400(user, llm, files(("empty.pdf", b"")), "is empty")

    async def test_page_out_of_range(self, user, llm):
        llm.plan = [{"operation": "split", "parameters": {"page_ranges": [[5, 9]], "merge": True}}]
        await self._expect_400(user, llm, files(("short.pdf", pdf(2))), "page numbers")

    async def test_instruction_too_long_is_a_validation_error(self, user, llm):
        resp = await process(user, files(("a.pdf", pdf(1))), "x" * 2001)
        assert resp.status_code == 422
        assert not llm.calls

    async def test_llm_outage_passes_through_as_503(self, user, llm):
        llm.error = HTTPException(status_code=503, detail="LLM service unavailable.")
        resp = await process(user, files(("a.pdf", pdf(1))))
        assert resp.status_code == 503
        assert await documents() == []

    async def test_unexpected_failure_is_a_generic_500(self, user, llm, captured_logs):
        with patch(
            "backend.routers.llm_router.execute_operation_chain",
            side_effect=RuntimeError("secret internal path /srv/x"),
        ):
            resp = await process(user, files(("a.pdf", pdf(1))))

        assert resp.status_code == 500
        assert "secret internal path" not in resp.text
        assert "pdf_processing_failed" in captured_logs.getvalue()


async def test_uploads_are_written_inside_the_upload_dir(user, llm):
    """Uploaded names never become paths: files are stored under random ids."""
    seen: list[Path] = []

    def record(operations, input_paths, *args):
        seen.extend(input_paths)
        out = input_paths[0].parent / "out.pdf"
        out.write_bytes(pdf(1))
        return out

    with patch("backend.routers.llm_router.execute_operation_chain", side_effect=record):
        await process(user, files(("../../escape.pdf", pdf(1))))

    assert seen
    for path in seen:
        assert path.resolve().parent == UPLOAD_DIR.resolve()
        assert "escape" not in path.name
