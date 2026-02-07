"""Middleware for session and authentication handling."""

from datetime import datetime, timezone

from litestar.middleware import AbstractMiddleware
from litestar.types import Receive, Scope, Send

from core.auth import AuthenticatedUser
import core.db as db


class SessionMiddleware(AbstractMiddleware):
    """Middleware to validate session cookies and populate user in scope."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract session_id from cookies
        session_id = self._get_session_cookie(scope)

        if session_id and db.pool:
            user = await self._validate_session(session_id)
            if user:
                scope["user"] = user

        await self.app(scope, receive, send)

    def _get_session_cookie(self, scope: Scope) -> str | None:
        """Extract session_id from request cookies."""
        headers = dict(scope.get("headers", []))
        cookie_header = headers.get(b"cookie", b"").decode()

        if not cookie_header:
            return None

        for cookie in cookie_header.split(";"):
            cookie = cookie.strip()
            if cookie.startswith("session_id="):
                return cookie.split("=", 1)[1]

        return None

    async def _validate_session(self, session_id: str) -> AuthenticatedUser | None:
        """Validate session and return user if valid."""
        if not db.pool:
            return None

        async with db.pool.connection() as conn:
            async with conn.cursor() as cur:
                # Get session with user data
                await cur.execute(
                    """
                    SELECT
                        s.expires,
                        s.inactive,
                        u.id,
                        u.username,
                        u.full_name,
                        u.inactive AS user_inactive
                    FROM sessions s
                    JOIN users u ON u.id = s.userid
                    WHERE s.id = %(session_id)s
                    """,
                    {"session_id": session_id},
                )
                row = await cur.fetchone()

                if not row:
                    return None

                expires, session_inactive, user_id, username, full_name, user_inactive = row

                # Check session validity
                if session_inactive or user_inactive:
                    return None

                # Compare with UTC now (column is timestamp without time zone but stores UTC)
                if expires and expires < datetime.now(timezone.utc).replace(tzinfo=None):
                    return None

                # Get user capabilities
                await cur.execute(
                    """
                    SELECT DISTINCT c.cap_name
                    FROM capabilities c
                    JOIN rolecapabilities rc ON rc.capabilityid = c.id
                    JOIN userroles ur ON ur.roleid = rc.roleid
                    WHERE ur.userid = %(user_id)s
                    """,
                    {"user_id": user_id},
                )
                cap_rows = await cur.fetchall()
                capabilities = {row[0] for row in cap_rows}

                return AuthenticatedUser(
                    id=str(user_id),
                    username=username,
                    full_name=full_name,
                    capabilities=capabilities,
                )
