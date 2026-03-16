"""Password and OTP hashing utilities."""

import hashlib

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_ph = PasswordHasher()
DUMMY_HASH = _ph.hash("timing_mitigation_pass")

# Fixed-length dummy for timing-safe OTP comparisons when user doesn't exist
DUMMY_OTP_HASH = "0" * 64


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_otp(code: str) -> str:
    """Hash a 6-digit OTP using SHA-256.

    Fast hashing is acceptable here because OTPs are short-lived (10 min)
    and attempt-limited (5 tries), so brute-force is already mitigated.
    """
    return hashlib.sha256(code.encode()).hexdigest()
