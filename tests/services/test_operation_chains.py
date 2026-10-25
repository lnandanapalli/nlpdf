"""execute_operation_chain end to end with the real PDF services (no mocks)."""

from pathlib import Path
import zipfile

from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter
import pytest

from backend.schemas.llm_schema import validate_llm_json_list
from backend.services.operations_executor_service import (
    MAX_OPERATIONS_PER_CHAIN,
    execute_operation_chain,
)


def make_pdf(path: Path, pages: int) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    with path.open("wb") as f:
        writer.write(f)
    return path


def ops(*items: dict):
    return validate_llm_json_list(list(items))


COMPRESS = {"operation": "compress", "parameters": {"level": 2}}
MERGE = {"operation": "merge", "parameters": {}}


def rotate(page: int, angle: int = 90) -> dict:
    return {"operation": "rotate", "parameters": {"rotations": [[page, angle]]}}


def split(ranges: list[list[int]], *, merge: bool) -> dict:
    return {"operation": "split", "parameters": {"page_ranges": ranges, "merge": merge}}


@pytest.fixture
def out_dir(tmp_path: Path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d


def test_merge_rotate_compress_chain(tmp_path, out_dir):
    a = make_pdf(tmp_path / "a.pdf", 2)
    b = make_pdf(tmp_path / "b.pdf", 1)

    result = execute_operation_chain(
        ops(MERGE, rotate(3, 180), COMPRESS), [a, b], out_dir, "documents"
    )

    reader = PdfReader(result)
    assert [p.rotation for p in reader.pages] == [0, 0, 180]
    # Intermediate step files are cleaned up; only the final output remains.
    assert sorted(p.name for p in out_dir.iterdir() if p.is_file()) == [result.name]


def test_bulk_compress_zips_one_result_per_input_named_after_it(tmp_path, out_dir):
    inputs = [make_pdf(tmp_path / f"{n}.pdf", 1) for n in ("alpha", "beta")]

    result = execute_operation_chain(ops(COMPRESS), inputs, out_dir, "documents", ["alpha", "beta"])

    with zipfile.ZipFile(result) as zf:
        assert sorted(zf.namelist()) == ["compress_alpha.pdf", "compress_beta.pdf"]


def test_bulk_markdown_then_merge(tmp_path, out_dir):
    inputs = []
    for name in ("one", "two"):
        path = tmp_path / f"{name}.md"
        path.write_text(f"# {name}\n\ntext\n", encoding="utf-8")
        inputs.append(path)

    result = execute_operation_chain(
        ops({"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}}, MERGE),
        inputs,
        out_dir,
    )

    assert result.suffix == ".pdf"
    assert len(PdfReader(result).pages) >= 2


def test_rotate_then_split_into_files(tmp_path, out_dir):
    src = make_pdf(tmp_path / "doc.pdf", 4)

    result = execute_operation_chain(
        ops(rotate(1), split([[1, 2], [3, 4]], merge=False)), [src], out_dir, "doc"
    )

    with zipfile.ZipFile(result) as zf:
        assert len(zf.namelist()) == 2


def test_too_many_steps_is_refused(tmp_path, out_dir):
    src = make_pdf(tmp_path / "doc.pdf", 1)
    with pytest.raises(HTTPException) as exc_info:
        execute_operation_chain(ops(*[COMPRESS] * (MAX_OPERATIONS_PER_CHAIN + 1)), [src], out_dir)
    assert exc_info.value.status_code == 400


def test_page_numbers_beyond_the_document_are_a_400_not_a_500(tmp_path, out_dir):
    src = make_pdf(tmp_path / "doc.pdf", 2)
    with pytest.raises(HTTPException) as exc_info:
        execute_operation_chain(ops(rotate(9)), [src], out_dir)
    assert exc_info.value.status_code == 400


def test_markdown_operation_on_a_pdf_is_refused(tmp_path, out_dir):
    src = make_pdf(tmp_path / "doc.pdf", 1)
    with pytest.raises(HTTPException) as exc_info:
        execute_operation_chain(
            ops({"operation": "markdown_to_pdf", "parameters": {}}), [src], out_dir
        )
    assert exc_info.value.status_code == 400
