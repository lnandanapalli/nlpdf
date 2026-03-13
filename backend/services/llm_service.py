"""HuggingFace Inference API integration."""

import asyncio
import json
from typing import Any

from fastapi import HTTPException, status
import httpx
from huggingface_hub import AsyncInferenceClient
import structlog

from backend.config import settings
from backend.prompts import SYSTEM_PROMPT
from backend.schemas.llm_schema import OperationType, validate_llm_json_list

logger = structlog.get_logger(__name__)


class LLMService:
    """Service for interacting with HuggingFace Inference API."""

    def __init__(self) -> None:
        """Initialise the HuggingFace async inference client."""
        self.client = AsyncInferenceClient(
            token=settings.HUGGINGFACE_API_TOKEN,
            timeout=settings.HUGGINGFACE_TIMEOUT,
        )
        self.model = settings.HUGGINGFACE_MODEL

    async def _call_llm(
        self,
        user_message: str,
        pdf_metadata: dict[str, Any] | None = None,
        retry_context: str | None = None,
    ) -> str:
        """Single LLM API call.

        Tries HuggingFace first; falls back to OpenAI
        only if HuggingFace returns a 429 rate-limit error and OPENAI_API_KEY
        is configured. Returns raw text response.

        Raises:
            HTTPException: If all available providers fail.
        """
        prompt_parts = [f"User request: {user_message}"]

        if pdf_metadata:
            file_count = pdf_metadata.get("file_count", 1)
            prompt_parts.append(
                f"PDF info: {file_count} file(s), "
                f"{pdf_metadata.get('total_page_count', '?')} pages total, "
                f"{pdf_metadata.get('total_file_size_mb', '?')} MB total"
            )

        if retry_context:
            prompt_parts.append(
                f"\nPrevious attempt produced invalid output: "
                f"{retry_context}\n"
                "Please fix the JSON and respond again."
            )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(prompt_parts)},
        ]

        try:
            response = await self.client.chat_completion(
                messages=messages,
                model=self.model,
                max_tokens=settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE,
            )
            content = response.choices[0].message.content
            if content is None:
                msg = "LLM returned empty content"
                raise ValueError(msg)  # noqa: TRY301 — extracted is more confusing here
            return content.strip()
        except Exception as e:  # BLE001: LLM SDK + HTTP can raise many types;
            # we log+fall-back to OpenAI or raise 503, so the broad catch is intentional
            if settings.OPENAI_API_KEY:
                logger.warning("HuggingFace failed (%s). Falling back to OpenAI.", e)
                return await self._call_openai(messages)
            logger.exception("LLM API call failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service unavailable. Please try again later.",
            ) from None

    async def _call_openai(self, messages: list[dict]) -> str:
        """OpenAI Chat Completions fallback call.

        Raises:
            HTTPException: If the OpenAI call fails.
        """
        payload = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "max_tokens": settings.LLM_MAX_TOKENS,
            "temperature": settings.LLM_TEMPERATURE,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json=payload,
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            if not content:
                msg = "OpenAI returned empty content"
                raise ValueError(msg)  # noqa: TRY301 — extracted is more confusing here
            logger.info("LLM response from OpenAI fallback")
            return content.strip()
        except Exception:  # BLE001 — httpx + OpenAI response errors are diverse
            logger.exception("OpenAI fallback failed")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service unavailable. Please try again later.",
            ) from None

    async def process_message(
        self,
        user_message: str,
        pdf_metadata: dict[str, Any] | None = None,
    ) -> list[OperationType]:
        """Generate and validate operations from a user message.

        Retries up to LLM_MAX_RETRIES times on parse/validation
        failures, feeding the error back to the LLM each time.

        Returns:
            A list of fully validated, typed operation models.

        Raises:
            HTTPException: On LLM errors or if all retries exhausted.
        """
        max_retries = settings.LLM_MAX_RETRIES
        retry_context: str | None = None

        for attempt in range(1, max_retries + 1):
            # Step 1: Call LLM
            raw = await self._call_llm(user_message, pdf_metadata, retry_context)
            logger.info("LLM attempt %d/%d raw: %s", attempt, max_retries, raw)

            # Step 2: Parse JSON
            cleaned = _extract_json(raw)
            parsed = _parse_json(cleaned)

            if parsed is None:
                retry_context = f"Response was not valid JSON: {cleaned!r}"
                logger.warning("Attempt %d: %s", attempt, retry_context)
                await asyncio.sleep(settings.LLM_RETRY_DELAY)
                continue

            # Normalize: wrap a single dict in a list
            if isinstance(parsed, dict):
                parsed = [parsed]

            if not isinstance(parsed, list):
                retry_context = "Response must be a JSON array of operations"
                logger.warning("Attempt %d: %s", attempt, retry_context)
                await asyncio.sleep(settings.LLM_RETRY_DELAY)
                continue

            # Step 3: Check if LLM returned an error object
            if any("error" in item for item in parsed):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This operation cannot be performed. "
                        "Please describe a valid PDF operation."
                    ),
                )

            # Step 4: Validate against operation schemas
            try:
                operations = validate_llm_json_list(parsed)
            except ValueError as e:
                retry_context = str(e)
                logger.warning("Attempt %d: %s", attempt, retry_context)
                await asyncio.sleep(settings.LLM_RETRY_DELAY)
                continue

            op_names = [op.operation for op in operations]
            logger.info("Validated operations: %s", op_names)
            return operations

        logger.error(
            "LLM failed after %d attempts. Last issue: %s",
            max_retries,
            retry_context,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not understand your request. " "Please try rephrasing your instruction.",
        )


def _extract_json(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    if "```json" in text:
        return text.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return text.strip()


def _parse_json(text: str) -> Any:
    """
    Parse JSON, with fallback for multi-line JSON objects.

    Some LLMs return one JSON object per line instead of a proper array.
    If standard parsing fails, try joining lines into an array.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: try parsing each non-empty line as a separate JSON object
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 1:
        try:
            return [json.loads(line) for line in lines]
        except json.JSONDecodeError:
            pass

    return None


# Module-level singleton — instantiated lazily on first request
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Dependency: return (and lazily create) the application LLM Service."""
    global _llm_service  # noqa: PLW0603 — intentional module-level singleton
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
