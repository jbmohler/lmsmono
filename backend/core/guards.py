from typing import Any

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException, PermissionDeniedException
from litestar.handlers import BaseRouteHandler


def require_capability(capability: str) -> Any:
    """Guard factory that checks if user has the required capability.

    Usage:
        @get(guards=[require_capability("contacts:read")])
        async def list_contacts(self) -> MultiRowResponse:
            ...
    """

    async def guard(connection: ASGIConnection, _: BaseRouteHandler) -> None:
        user = connection.scope.get("user")
        if not user:
            raise NotAuthorizedException(detail="Not authenticated")

        capabilities: set[str] = getattr(user, "capabilities", set())
        if capability not in capabilities:
            raise PermissionDeniedException(detail=f"Missing capability: {capability}")

    return guard
