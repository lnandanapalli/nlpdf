"""Tests for the LLM service (extract_json helper and process_message)."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from backend.services.llm_service import _extract_json

# ── _extract_json ────────────────────────────────────────────────────────────


class TestExtractJson:
    """Tests for _extract_json helper."""

    def test_plain_json(self):
        text = '{"operation": "compress", "parameters": {"level": 2}}'
        assert json.loads(_extract_json(text)) == {
            "operation": "compress",
            "parameters": {"level": 2},
        }

    def test_json_code_fence(self):
        text = '```json\n{"operation": "merge", "parameters": {}}\n```'
        result = _extract_json(text)
        assert json.loads(result) == {"operation": "merge", "parameters": {}}

    def test_bare_code_fence(self):
        text = (
            '```\n{"operation": "rotate", "parameters": {"rotations": [[1, 90]]}}\n```'
        )
        result = _extract_json(text)
        parsed = json.loads(result)
        assert parsed["operation"] == "rotate"

    def test_surrounding_whitespace(self):
        text = '  \n  {"key": "value"}  \n  '
        result = _extract_json(text)
        assert json.loads(result) == {"key": "value"}


# ── LLMService.process_message ───────────────────────────────────────────────


class TestProcessMessage:
    """Tests for LLMService.process_message with mocked LLM calls."""

    @pytest.fixture()
    def llm_service(self):
        """Create LLMService with a mocked client."""
        with patch("backend.services.llm_service.settings") as mock_settings:
            mock_settings.HUGGINGFACE_API_TOKEN = "test-token"
            mock_settings.HUGGINGFACE_TIMEOUT = 10
            mock_settings.HUGGINGFACE_MODEL = "test-model"
            mock_settings.LLM_MAX_RETRIES = 3
            mock_settings.LLM_RETRY_DELAY = 0.0  # no delay in tests
            mock_settings.LLM_MAX_TOKENS = 256
            mock_settings.LLM_TEMPERATURE = 0.01

            from backend.services.llm_service import LLMService

            service = LLMService.__new__(LLMService)
            service.client = AsyncMock()
            service.model = "test-model"
            yield service

    async def test_valid_json_first_attempt(self, llm_service):
        response_json = '[{"operation": "compress", "parameters": {"level": 2}}]'
        llm_service._call_llm = AsyncMock(return_value=response_json)

        result = await llm_service.process_message("compress this pdf")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].operation == "compress"
        assert result[0].parameters.level == 2

    async def test_fallback_single_object_wrapped_in_list(self, llm_service):
        # LLM returns a plain object instead of an array
        response_json = (
            '{"operation": "rotate", "parameters": {"rotations": [[1, 90]]}}'
        )
        llm_service._call_llm = AsyncMock(return_value=response_json)

        result = await llm_service.process_message("rotate page 1")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].operation == "rotate"
        assert result[0].parameters.rotations == [(1, 90)]

    async def test_fallback_multiline_json_objects(self, llm_service):
        # LLM returns separated objects on new lines (the chained operation edge case)
        response_json = (
            '{"operation": "merge", "parameters": {}}\n'
            '{"operation": "rotate", "parameters": {"rotations": [[2, 90]]}}'
        )
        llm_service._call_llm = AsyncMock(return_value=response_json)

        result = await llm_service.process_message("merge and rotate")

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0].operation == "merge"
        assert result[1].operation == "rotate"
        assert result[1].parameters.rotations == [(2, 90)]

    async def test_retry_on_invalid_json_then_succeed(self, llm_service):
        llm_service._call_llm = AsyncMock(
            side_effect=[
                "not valid json",
                '[{"operation": "merge", "parameters": {}}]',
            ]
        )

        result = await llm_service.process_message("merge files")

        assert len(result) == 1
        assert result[0].operation == "merge"
        assert llm_service._call_llm.call_count == 2

    async def test_llm_error_object_raises_400(self, llm_service):
        llm_service._call_llm = AsyncMock(return_value='[{"error": "Cannot do that"}]')

        with pytest.raises(HTTPException) as exc_info:
            await llm_service.process_message("do something impossible")

        assert exc_info.value.status_code == 400
        assert "Please describe a valid PDF operation" in exc_info.value.detail

    async def test_all_retries_exhausted_raises_500(self, llm_service):
        llm_service._call_llm = AsyncMock(return_value="invalid json forever")

        with pytest.raises(HTTPException) as exc_info:
            await llm_service.process_message("compress this")

        assert exc_info.value.status_code == 500
        assert "Failed to produce" in exc_info.value.detail
