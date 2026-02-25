"""HuggingFace Inference API integration."""

import asyncio
import json
import logging
from typing import Any

from fastapi import HTTPException
from huggingface_hub import AsyncInferenceClient

from backend.config import SYSTEM_PROMPT, settings
from backend.schemas.llm_schema import OperationType, validate_llm_json

logger = logging.getLogger("nlpdf.llm")


class LLMService:
    """Service for interacting with HuggingFace Inference API."""

    def __init__(self):
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
        """
        Single LLM API call. Returns raw text response.

        Raises:
            HTTPException: If the API call fails.
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
                raise ValueError("LLM returned empty content")
            return content.strip()
        except Exception as e:
            logger.error("LLM API call failed: %s", e)
            raise HTTPException(
                status_code=503,
                detail="LLM service unavailable. Please try again later.",
            )

    async def process_message(
        self,
        user_message: str,
        pdf_metadata: dict[str, Any] | None = None,
    ) -> OperationType:
        """
        Generate and validate an operation from a user message.

        Retries up to LLM_MAX_RETRIES times on parse/validation
        failures, feeding the error back to the LLM each time.

        Returns:
            A fully validated, typed operation model.

        Raises:
            HTTPException: On LLM errors or if all retries exhausted.
        """
        max_retries = settings.LLM_MAX_RETRIES
        retry_context: str | None = None

        for attempt in range(1, max_retries + 1):
            # Step 1: Call LLM
            raw = await self._call_llm(user_message, pdf_metadata, retry_context)
            logger.info("LLM attempt %d/%d raw: %s", attempt, max_retries, raw)

            # Step 2: Parse JSON (strip code fences if LLM wraps them)
            cleaned = _extract_json(raw)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as e:
                retry_context = f"Response was not valid JSON: {e}"
                logger.warning("Attempt %d: %s", attempt, retry_context)
                await asyncio.sleep(settings.LLM_RETRY_DELAY)
                continue

            # Step 3: Check if LLM returned an error object
            if "error" in parsed:
                # Security: NEVER pass the LLM's raw text to the user
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "This operation cannot be performed. "
                        "Please describe a valid PDF operation."
                    ),
                )

            # Step 4: Validate against operation schemas
            try:
                operation = validate_llm_json(parsed)
            except ValueError as e:
                retry_context = str(e)
                logger.warning("Attempt %d: %s", attempt, retry_context)
                await asyncio.sleep(settings.LLM_RETRY_DELAY)
                continue

            logger.info("Validated operation: %s", operation.operation)
            return operation

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to produce a valid operation "
                f"after {max_retries} attempts. "
                f"Last issue: {retry_context}"
            ),
        )


def _extract_json(text: str) -> str:
    """Strip markdown code fences from LLM output."""
    if "```json" in text:
        return text.split("```json", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return text.strip()


# Cache the LLMService singleton manually or recreate it per request if lightweight.
# We hold a single instance here so that dependency injection always yields the same
# configured inference client rather than instantiating it per inference.
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Dependency: Yields the application LLM Service."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
