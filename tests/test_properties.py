"""Property-based tests: untrusted input must be accepted correctly or refused cleanly.

The LLM's reply, page ranges and forwarded IPs all come from outside the
server. For any value, the code must either produce a valid result or raise
its documented error -- never crash with something unexpected (a 500).
"""

import contextlib
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from pypdf import PdfReader, PdfWriter
import pytest

from backend.schemas.split_schema import SplitParams
from backend.security import get_client_ip
from backend.services.llm_service import LLMService
from backend.services.split_service import split_pdf
from backend.validators.page_validators import validate_page_ranges

ALLOWED = {"compress", "split", "rotate", "merge", "markdown_to_pdf"}

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=20),
    lambda children: st.lists(children, max_size=4)
    | st.dictionaries(st.text(max_size=12), children, max_size=4),
    max_leaves=20,
)

# Shapes close to a real reply, so the generator reaches the schema checks
# instead of failing on the outer structure every time.
operation_like = st.fixed_dictionaries(
    {
        "operation": st.sampled_from(
            ["compress", "split", "rotate", "merge", "markdown_to_pdf", "x"]
        ),
        "parameters": json_values,
    }
)


@pytest.fixture(scope="module")
def llm_service():
    with patch("backend.services.llm_service.settings") as fake:
        fake.LLM_MAX_RETRIES = 2
        fake.LLM_RETRY_DELAY = 0.0
        service = LLMService.__new__(LLMService)
        service.client = MagicMock()
        service.model = "fuzz"
        yield service


@settings(max_examples=300, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(reply=st.one_of(json_values, st.lists(operation_like, max_size=4), operation_like))
async def test_any_llm_reply_is_validated_or_refused(llm_service, reply):
    llm_service._call_llm = AsyncMock(return_value=json.dumps(reply))
    try:
        operations = await llm_service.process_message("fuzz")
        status = 200
    except HTTPException as exc:
        operations, status = [], exc.status_code
    assert status in (200, 400)
    assert status == 400 or operations
    assert all(op.operation in ALLOWED for op in operations)


@settings(max_examples=200)
@given(raw=st.text(max_size=200))
async def test_any_text_reply_is_validated_or_refused(raw):
    with patch("backend.services.llm_service.settings") as fake:
        fake.LLM_MAX_RETRIES = 1
        fake.LLM_RETRY_DELAY = 0.0
        service = LLMService.__new__(LLMService)
        service._call_llm = AsyncMock(return_value=raw)
        status = 200
        try:
            await service.process_message("fuzz")
        except HTTPException as exc:
            status = exc.status_code
        assert status in (200, 400)


@given(ranges=st.lists(st.tuples(st.integers(-5, 60_000), st.integers(-5, 60_000)), max_size=120))
def test_page_ranges_are_accepted_only_when_sane(ranges):
    try:
        result = validate_page_ranges(ranges)
    except ValueError:
        return
    assert 1 <= len(result) <= 100
    for start, end in result:
        assert 1 <= start <= end


@given(ranges=st.lists(st.tuples(st.integers(), st.integers()), max_size=5), merge=st.booleans())
def test_split_params_never_raise_anything_but_validation_errors(ranges, merge):
    with contextlib.suppress(ValidationError):
        SplitParams(page_ranges=ranges, merge=merge)


def _pdf(path: Path, pages: int) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    with path.open("wb") as f:
        writer.write(f)
    return path


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    pages=st.integers(1, 8),
    data=st.data(),
)
def test_merged_split_has_exactly_the_requested_pages(tmp_path, pages, data):
    """Whatever valid ranges are asked for, the output has exactly those pages."""
    ranges = data.draw(
        st.lists(
            st.integers(1, pages).flatmap(lambda s: st.tuples(st.just(s), st.integers(s, pages))),
            min_size=1,
            max_size=5,
        )
    )
    src = _pdf(tmp_path / f"src{pages}.pdf", pages)
    out = tmp_path / "out.pdf"

    split_pdf(src, ranges, True, out, "doc")

    expected = sum(end - start + 1 for start, end in ranges)
    assert len(PdfReader(io.BytesIO(out.read_bytes())).pages) == expected


@given(header=st.text(max_size=100))
def test_client_ip_never_crashes_and_takes_one_entry(header):
    request = MagicMock()
    request.headers = {"X-Forwarded-For": header}
    request.client.host = "10.0.0.1"  # the fallback for an empty header
    ip = get_client_ip(request)
    assert isinstance(ip, str)
    assert "," not in ip
