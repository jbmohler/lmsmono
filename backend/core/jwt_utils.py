"""JWT utilities for password reset tokens."""

from datetime import datetime, timedelta, timezone

import jwt


RESET_TOKEN_EXPIRY_HOURS = 2
RESET_PURPOSE = "password_reset"


def create_reset_token(user_id: str, secret_key: str) -> str:
    """Create a signed JWT for password reset, valid for 2 hours."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "purpose": RESET_PURPOSE,
        "iat": now,
        "exp": now + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_reset_token(token: str, secret_key: str) -> str:
    """Decode and validate a password reset JWT.

    Returns the user_id (sub claim) on success.
    Raises jwt.InvalidTokenError (or subclass) on failure.
    """
    payload = jwt.decode(token, secret_key, algorithms=["HS256"])

    if payload.get("purpose") != RESET_PURPOSE:
        raise jwt.InvalidTokenError("Token is not a password reset token")

    return str(payload["sub"])
