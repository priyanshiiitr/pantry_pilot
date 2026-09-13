"""Tests for password hashing (pantrypilot/auth/passwords.py)."""

import pytest

from pantrypilot.auth.passwords import hash_password, verify_password


def test_hash_is_not_the_plain_password() -> None:
    """The stored hash must never contain the real password."""
    password_hash = hash_password("demo1234")

    assert password_hash != "demo1234"
    assert "demo1234" not in password_hash


def test_correct_password_verifies() -> None:
    """The right password matches its hash."""
    password_hash = hash_password("demo1234")

    assert verify_password("demo1234", password_hash) is True


def test_wrong_password_is_rejected() -> None:
    """A different password does not match."""
    password_hash = hash_password("demo1234")

    assert verify_password("wrong-password", password_hash) is False


def test_too_long_password_is_refused() -> None:
    """bcrypt can't handle more than 72 bytes, so we refuse clearly instead of crashing later."""
    with pytest.raises(ValueError):
        hash_password("x" * 73)
