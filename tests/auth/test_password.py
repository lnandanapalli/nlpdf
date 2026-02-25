"""Tests for password hashing and verification."""

from backend.auth.password import hash_password, verify_password


class TestHashPassword:
    """Tests for hash_password."""

    def test_returns_hash_string(self):
        result = hash_password("mysecret")
        assert isinstance(result, str)
        assert result != "mysecret"

    def test_different_calls_produce_different_hashes(self):
        h1 = hash_password("same_password")
        h2 = hash_password("same_password")
        assert h1 != h2  # bcrypt uses random salt


class TestVerifyPassword:
    """Tests for verify_password."""

    def test_correct_password_returns_true(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_wrong_password_returns_false(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_empty_password_returns_false(self):
        hashed = hash_password("notempty")
        assert verify_password("", hashed) is False
