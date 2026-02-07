"""Password hashing utilities using Argon2."""

import argon2

_hasher = argon2.PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return _hasher.hash(password)


def verify_password(password: str, hash: str) -> bool:
    """Verify a password against a hash.

    Returns True if the password matches, False otherwise.
    """
    try:
        _hasher.verify(hash, password)
        return True
    except argon2.exceptions.VerifyMismatchError:
        return False
