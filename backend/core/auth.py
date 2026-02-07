"""Authentication types and utilities."""

from dataclasses import dataclass, field


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user in the request scope."""

    id: str
    username: str
    full_name: str | None
    capabilities: set[str] = field(default_factory=set)
