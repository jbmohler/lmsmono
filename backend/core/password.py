"""Password hashing utilities using Argon2."""

import argon2

_hasher = argon2.PasswordHasher()

# Verified against on login paths where there is no real hash to check, so that
# a missing/unset account costs the same wall time as a wrong password.
_dummy_hash = _hasher.hash("dummy password for login timing equalization")


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


def verify_dummy_password(password: str) -> None:
    """Burn an Argon2 verify against a throwaway hash.

    Used on login failure paths that have no stored hash to check, so response
    timing does not reveal whether the username exists.
    """
    try:
        _hasher.verify(_dummy_hash, password)
    except argon2.exceptions.VerifyMismatchError:
        pass
