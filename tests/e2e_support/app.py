"""Backend entry point for the Playwright end-to-end suite. Never deploy this.

It is the real application (database, auth, CSRF, PDF pipeline) with only the
third parties replaced:

- the LLM, by a deterministic fake that still goes through the real JSON
  parsing and operation validation in LLMService.process_message;
- outgoing email, by an in-memory outbox the tests read codes from;
- the server-side Turnstile check (the browser still runs the widget with
  Cloudflare's always-pass test key).

Test-only routes live under /__e2e__ and exist only in this module.

Run with:  uvicorn tests.e2e_support.app:app --port 8001
"""

import json
import re
from unittest.mock import patch

from fastapi import HTTPException, status
from sqlalchemy import select

from backend.config import settings

if settings.APP_ENV == "production":  # pragma: no cover - safety net
    raise RuntimeError("The e2e app must never run with APP_ENV=production")

from backend.database import AsyncSessionLocal
from backend.main import app
from backend.models.user import User
from backend.rate_limit import limiter
from backend.routers import auth_router
from backend.services.llm_service import LLMService, get_llm_service

# Every e2e account uses this shape, so cleanup can never touch real users.
E2E_EMAIL_PATTERN = re.compile(r"^e2e-[a-z0-9-]+@example\.com$")

# Many tests share one IP; the per-IP limits would make them flaky.
limiter.enabled = False

# ---------------------------------------------------------------------------
# Email: capture codes instead of sending them
# ---------------------------------------------------------------------------

_outbox: dict[str, str] = {}


def _capture(to_email: str, otp_code: str) -> None:
    _outbox[to_email.lower()] = otp_code


# Patched for the life of the process; this module is only ever a test server.
for _sender in (
    "send_otp_email",
    "send_password_reset_otp_email",
    "send_account_deletion_otp_email",
):
    patch.object(auth_router, _sender, _capture).start()


async def _accept_turnstile(token: str) -> bool:
    return bool(token)


patch.object(auth_router, "verify_turnstile", _accept_turnstile).start()

# ---------------------------------------------------------------------------
# LLM: a tiny deterministic grammar instead of a model
# ---------------------------------------------------------------------------

OUTAGE_PHRASE = "simulate llm outage"


def _plan(message: str) -> list[dict]:
    """Translate a test instruction into the operations JSON a model would emit.

    Steps are separated by " then ". Unknown wording yields the same error
    object the real prompt asks the model for.
    """
    operations: list[dict] = []
    for step in message.lower().split(" then "):
        if m := re.search(r"extract pages (\d+)-(\d+)", step):
            ranges = [[int(m[1]), int(m[2])]]
            operations.append(
                {"operation": "split", "parameters": {"page_ranges": ranges, "merge": True}}
            )
        elif m := re.search(r"split pages (\d+)-(\d+) and (\d+)-(\d+) separately", step):
            ranges = [[int(m[1]), int(m[2])], [int(m[3]), int(m[4])]]
            operations.append(
                {"operation": "split", "parameters": {"page_ranges": ranges, "merge": False}}
            )
        elif m := re.search(r"rotate page (\d+)", step):
            operations.append(
                {"operation": "rotate", "parameters": {"rotations": [[int(m[1]), 90]]}}
            )
        elif "compress" in step:
            operations.append({"operation": "compress", "parameters": {"level": 2}})
        elif "merge" in step:
            operations.append({"operation": "merge", "parameters": {}})
        elif "convert" in step:
            operations.append({"operation": "markdown_to_pdf", "parameters": {"paper_size": "A4"}})
        else:
            return [{"error": "invalid_operation"}]
    return operations


class FakeLLMService(LLMService):
    """LLMService whose model call is replaced; parsing and validation are real."""

    def __init__(self) -> None:  # no HuggingFace client
        self.model = "e2e-fake"

    async def _call_llm(self, user_message, pdf_metadata=None, retry_context=None) -> str:
        if OUTAGE_PHRASE in user_message.lower():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="LLM service unavailable. Please try again later.",
            )
        return json.dumps(_plan(user_message))


_fake_llm = FakeLLMService()
app.dependency_overrides[get_llm_service] = lambda: _fake_llm

# ---------------------------------------------------------------------------
# Test-only routes
# ---------------------------------------------------------------------------


def _require_e2e_email(email: str) -> str:
    email = email.lower()
    if not E2E_EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="Not an e2e test address")
    return email


@app.get("/__e2e__/outbox/{email}", include_in_schema=False)
async def read_outbox(email: str) -> dict[str, str]:
    """Return, and consume, the most recent code emailed to an e2e test address.

    Consuming it means a test waiting for the next email (a reset or
    deletion code after the signup one) can't pick up an older code.
    """
    code = _outbox.pop(_require_e2e_email(email), None)
    if code is None:
        raise HTTPException(status_code=404, detail="No email sent to that address")
    return {"code": code}


@app.get("/__e2e__/cleanup", include_in_schema=False)
async def cleanup() -> dict[str, int]:
    """Delete every e2e test account, with its sessions and history.

    Deletes through the ORM: the documents.owner_id CASCADE exists only in
    the model, not in the migrations, so a bulk DELETE would hit the FK.
    """
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        doomed = [u for u in users if E2E_EMAIL_PATTERN.match(u.email)]
        for user in doomed:
            await db.delete(user)
        await db.commit()
    _outbox.clear()
    return {"deleted": len(doomed)}
