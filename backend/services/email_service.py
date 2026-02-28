"""Service for sending emails via Resend."""

from typing import cast

import resend
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

resend.api_key = settings.RESEND_API_KEY


def send_otp_email(to_email: str, otp_code: str) -> None:
    """Send an OTP code to the provided email address."""
    html_content = f"""
    <h2>Verify your email</h2>
    <p>Your one-time password (OTP) is: <strong>{otp_code}</strong></p>
    <p>This code will expire in 10 minutes.</p>
    """

    params = cast(
        resend.Emails.SendParams,
        {
            "from": "NLPDF <noreply@nlpdf.online>",
            "to": to_email,
            "subject": "Your NLPDF Verification Code",
            "html": html_content,
        },
    )

    try:
        resend.Emails.send(params)
    except Exception as e:
        logger.error("Failed to send email", to_email=to_email, error=str(e))
