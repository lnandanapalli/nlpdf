import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: str) -> bool:
    """Verify a Cloudflare Turnstile token. Returns True if valid."""
    if not token:
        logger.warning("turnstile_verification_failed", reason="missing_token")
        return False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                SITEVERIFY_URL,
                data={
                    "secret": settings.CLOUDFLARE_TURNSTILE_SECRET_KEY,
                    "response": token,
                },
            )
            response.raise_for_status()
            result = response.json()
            success = bool(result.get("success", False))

            if not success:
                logger.warning(
                    "turnstile_verification_failed",
                    error_codes=result.get("error-codes"),
                )
            return success
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.exception("turnstile_network_error", error=str(exc))
        return False
