"""Remember-me device tokens.

A device token is a long-lived secret that lets a browser obtain a fresh
short-lived session without re-entering a password. The plaintext secret lives
only in the client's cookie; the database stores an Argon2 hash of it in
devicetokens.tokenhash (the same hashing used for user passwords).

Cookie format is ``<devtok_id>.<secret>``:

- ``devtok_id`` is the devicetokens.id primary key (32 hex chars), used to look
  up the single candidate row so verification never scans the table.
- ``secret`` is a 256-bit URL-safe random string; only its Argon2 hash is
  persisted, so a database leak does not expose usable tokens.
"""

import secrets
import uuid
from dataclasses import dataclass

from core.password import hash_password, verify_password


@dataclass
class MintedToken:
    """A freshly minted device token.

    ``cookie_value`` is handed to the client; ``devtok_id`` and ``tokenhash``
    are persisted in devicetokens.
    """

    devtok_id: str
    cookie_value: str
    tokenhash: str


def mint_token(devtok_id: str | None = None) -> MintedToken:
    """Create a device token secret and stored hash.

    Pass ``devtok_id`` to re-mint the secret for an existing token (rotation on
    refresh); omit it to allocate a brand-new token id at login.
    """
    if devtok_id is None:
        devtok_id = uuid.uuid4().hex
    secret = secrets.token_urlsafe(32)
    return MintedToken(
        devtok_id=devtok_id,
        cookie_value=f"{devtok_id}.{secret}",
        tokenhash=hash_password(secret),
    )


def split_cookie(raw: str | None) -> tuple[str, str] | None:
    """Parse a remember-me cookie into ``(devtok_id, secret)``.

    Returns None for any malformed value so a junk cookie behaves like an
    unknown token rather than raising, mirroring parse_session_id.
    """
    if not raw or "." not in raw:
        return None

    devtok_id, secret = raw.split(".", 1)
    if not devtok_id or not secret:
        return None

    try:
        # devtok_id must be a 32-hex-char uuid; reject anything else before it
        # reaches the character(32) primary-key column.
        uuid.UUID(hex=devtok_id)
    except ValueError:
        return None

    return devtok_id, secret


def verify_secret(secret: str, tokenhash: str) -> bool:
    """Check a presented secret against the stored Argon2 hash."""
    return verify_password(secret, tokenhash)
