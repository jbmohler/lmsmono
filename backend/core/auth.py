"""Authentication types and utilities."""

import uuid
from dataclasses import dataclass, field

from litestar import Request
from litestar.exceptions import NotAuthorizedException


def parse_session_id(raw: str | None) -> str | None:
    """Normalize a session cookie value to a canonical UUID string.

    Returns None when the value is missing or not a well-formed UUID. The
    sessions.id column is a uuid, so handing Postgres a malformed value raises
    instead of matching nothing - a junk cookie would 500 every request,
    including the SPA fallback that serves the login page. Screening it here
    makes a malformed id behave like a uuid that simply is not in the table.
    """
    if not raw:
        return None

    try:
        return str(uuid.UUID(raw))
    except ValueError:
        return None


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user in the request scope."""

    id: str
    username: str
    full_name: str | None
    capabilities: set[str] = field(default_factory=set)


async def provide_current_user(request: Request) -> AuthenticatedUser:
    """Dependency provider that returns the authenticated user from the request scope."""
    user = request.scope.get("user")
    if not user:
        raise NotAuthorizedException(detail="Not authenticated")
    return user
