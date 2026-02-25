"""Cloudflare Turnstile CAPTCHA verification service."""

import httpx

from backend.config import settings

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str) -> bool:
    """Verify a Cloudflare Turnstile token. Returns True if valid."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            SITEVERIFY_URL,
            data={
                "secret": settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
                "response": token,
            },
        )
        result = response.json()
        return bool(result.get("success", False))
