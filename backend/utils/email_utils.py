"""Email utilities for PII protection and formatting."""


def mask_email(email: str) -> str:
    """Mask PII in email addresses for logging."""
    if "@" not in email:
        return "invalid-email"
    user_part, domain_part = email.split("@", 1)
    return f"{user_part[:2]}****@{domain_part}"
