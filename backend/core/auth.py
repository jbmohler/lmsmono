"""Authentication types and utilities."""

from dataclasses import dataclass, field

from litestar import Request
from litestar.exceptions import NotAuthorizedException


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
