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
        "resend.Emails.SendParams",
        {
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "Your NLPDF Verification Code",
            "html": html_content,
        },
    )

    try:
        resend.Emails.send(params)
    except Exception:  # resend SDK raises unspecified exception types
        logger.exception("Failed to send email", to_email=to_email)


def send_account_deletion_otp_email(to_email: str, otp_code: str) -> None:
    """Send an OTP code for account deletion confirmation."""
    html_content = f"""
    <h2>Account Deletion Request</h2>
    <p>You have requested to delete your NLPDF account.</p>
    <p>Your confirmation code is: <strong>{otp_code}</strong></p>
    <p>This code will expire in 10 minutes.</p>
    <p>If you did not request this, please ignore this email and secure your account.</p>
    """

    params = cast(
        "resend.Emails.SendParams",
        {
            "from": settings.EMAIL_FROM,
            "to": to_email,
            "subject": "NLPDF Account Deletion Confirmation",
            "html": html_content,
        },
    )

    try:
        resend.Emails.send(params)
    except Exception:  # resend SDK raises unspecified exception types
        logger.exception("Failed to send deletion OTP email", to_email=to_email)
