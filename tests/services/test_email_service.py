"""Email sending: the right message goes out, and failures never leak codes."""

from unittest.mock import patch

import pytest

from backend.services import email_service

SENDERS = [
    (email_service.send_otp_email, "Verification"),
    (email_service.send_account_deletion_otp_email, "Deletion"),
    (email_service.send_password_reset_otp_email, "Reset"),
]


@pytest.mark.parametrize(("send", "subject_word"), SENDERS)
def test_sends_the_code_to_the_address(send, subject_word):
    with patch.object(email_service.resend.Emails, "send") as resend_send:
        send("someone@example.com", "482913")

    params = resend_send.call_args.args[0]
    assert params["to"] == "someone@example.com"
    assert params["from"] == email_service.settings.EMAIL_FROM
    assert subject_word.lower() in params["subject"].lower()
    assert "482913" in params["html"]


@pytest.mark.parametrize(("send", "_subject"), SENDERS)
def test_failure_is_logged_without_the_code_or_full_address(send, _subject, captured_logs):
    with patch.object(
        email_service.resend.Emails, "send", side_effect=RuntimeError("provider down")
    ):
        send("someone@example.com", "482913")  # must not raise into the request

    logged = captured_logs.getvalue()
    assert logged  # the failure is recorded
    assert "482913" not in logged
    assert "someone@example.com" not in logged
