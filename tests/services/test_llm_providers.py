"""The provider calls inside LLMService: prompt building, HuggingFace, OpenAI fallback."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import httpx
import pytest

from backend.prompts import SYSTEM_PROMPT
from backend.services import llm_service as module
from backend.services.llm_service import LLMService, get_llm_service


def hf_reply(content: str | None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


@pytest.fixture
def fake_settings():
    with patch.object(module, "settings") as s:
        s.OPENAI_API_KEY = None
        s.OPENAI_MODEL = "gpt-test"
        s.LLM_MAX_TOKENS = 64
        s.LLM_TEMPERATURE = 0.0
        yield s


@pytest.fixture
def service(fake_settings):
    svc = LLMService.__new__(LLMService)
    svc.client = MagicMock()
    svc.client.chat_completion = AsyncMock(return_value=hf_reply("  [ ]  "))
    svc.model = "hf-model"
    return svc


async def test_prompt_carries_the_request_file_facts_and_retry_feedback(service):
    await service._call_llm(
        "rotate page 2",
        {"file_count": 2, "total_page_count": 7, "total_file_size_mb": 1.5},
        retry_context="missing parameters",
    )

    kwargs = service.client.chat_completion.call_args.kwargs
    system, user = kwargs["messages"]
    assert system == {"role": "system", "content": SYSTEM_PROMPT}
    assert "User request: rotate page 2" in user["content"]
    assert "2 file(s), 7 pages total, 1.5 MB total" in user["content"]
    assert "missing parameters" in user["content"]
    assert kwargs["model"] == "hf-model"


async def test_reply_is_trimmed(service):
    assert await service._call_llm("x") == "[ ]"


async def test_empty_huggingface_reply_without_fallback_is_503(service):
    service.client.chat_completion = AsyncMock(return_value=hf_reply(None))
    with pytest.raises(HTTPException) as exc_info:
        await service._call_llm("x")
    assert exc_info.value.status_code == 503


async def test_any_huggingface_failure_uses_openai_when_configured(service, fake_settings):
    fake_settings.OPENAI_API_KEY = "sk-test"  # pragma: allowlist secret
    service.client.chat_completion = AsyncMock(side_effect=TimeoutError())
    service._call_openai = AsyncMock(return_value="[]")

    assert await service._call_llm("x") == "[]"
    service._call_openai.assert_awaited_once()


def _openai_transport(handler):
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(*args, **kwargs)

    return patch.object(module.httpx, "AsyncClient", side_effect=factory)


async def test_openai_call_sends_the_key_and_returns_the_text(service, fake_settings):
    fake_settings.OPENAI_API_KEY = "sk-test"  # pragma: allowlist secret
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = request.read()
        return httpx.Response(200, json={"choices": [{"message": {"content": " [1] "}}]})

    with _openai_transport(handler):
        result = await service._call_openai([{"role": "user", "content": "hi"}])

    assert result == "[1]"
    assert seen["auth"] == "Bearer sk-test"
    assert b'"model":"gpt-test"' in seen["body"].replace(b" ", b"")


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "down"}),
        httpx.Response(200, json={"choices": [{"message": {"content": ""}}]}),
        httpx.Response(200, json={"unexpected": True}),
    ],
)
async def test_openai_failures_become_503(service, fake_settings, response):
    fake_settings.OPENAI_API_KEY = "sk-test"  # pragma: allowlist secret
    with _openai_transport(lambda request: response), pytest.raises(HTTPException) as exc_info:
        await service._call_openai([{"role": "user", "content": "hi"}])
    assert exc_info.value.status_code == 503


def test_service_is_a_lazily_created_singleton():
    with (
        patch.object(module, "_llm_service", None),
        patch.object(module, "AsyncInferenceClient") as client_cls,
    ):
        first = get_llm_service()
        second = get_llm_service()
    assert first is second
    client_cls.assert_called_once()
