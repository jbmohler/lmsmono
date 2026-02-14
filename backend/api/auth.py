"""Authentication controller for login, logout, and session management."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
from litestar import Controller, Request, Response, get, post
from litestar.exceptions import NotAuthorizedException

from core.auth import AuthenticatedUser
from core.password import verify_password
from core.queries_admin import sql_select_user_capabilities


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_user_by_username() -> str:
    """Get user by username for login."""
    return """
        SELECT id, username, full_name, pwhash, inactive
        FROM users
        WHERE username = %(username)s
    """


def sql_insert_session() -> str:
    """Create a new session."""
    return """
        INSERT INTO sessions (id, userid, issued, expires)
        VALUES (%(id)s, %(userid)s, %(issued)s, %(expires)s)
    """


def sql_update_session_inactive() -> str:
    """Invalidate a session on logout."""
    return "UPDATE sessions SET inactive = true WHERE id = %(id)s"


@dataclass
class LoginRequest:
    username: str
    password: str


@dataclass
class UserResponse:
    id: str
    username: str
    full_name: str | None
    capabilities: list[str]


def _get_config():
    """Get app config from module-level variable in app.py."""
    import app

    return app.config


class AuthController(Controller):
    path = "/api/auth"
    tags = ["auth"]

    @post("/login")
    async def login(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
        data: LoginRequest,
    ) -> Response[UserResponse]:
        """Authenticate user and create session."""
        config = _get_config()

        # Look up user by username
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_by_username(),
                {"username": data.username},
            )
            row = await cur.fetchone()

        if not row:
            raise NotAuthorizedException(detail="Invalid username or password")

        user_id, username, full_name, pwhash, inactive = row

        if inactive:
            raise NotAuthorizedException(detail="Account is inactive")

        if not pwhash:
            raise NotAuthorizedException(detail="Password not set")

        if not verify_password(data.password, pwhash):
            raise NotAuthorizedException(detail="Invalid username or password")

        # Get user capabilities
        capabilities = await self._get_user_capabilities(conn, user_id)

        # Create session
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=config.session.expire_minutes)

        async with conn.cursor() as cur:
            await cur.execute(
                sql_insert_session(),
                {
                    "id": session_id,
                    "userid": user_id,
                    "issued": now,
                    "expires": expires,
                },
            )

        # Build response with cookie
        user_response = UserResponse(
            id=str(user_id),
            username=username,
            full_name=full_name,
            capabilities=sorted(capabilities),
        )

        response = Response(user_response)
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            secure=config.session.secure_cookie,
            samesite="strict",
            path="/",
            max_age=config.session.expire_minutes * 60,
        )

        return response

    @post("/logout")
    async def logout(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
    ) -> Response[dict]:
        """Invalidate session and clear cookie."""
        session_id = request.cookies.get("session_id")

        if session_id:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql_update_session_inactive(),
                    {"id": session_id},
                )

        response = Response({"ok": True})
        response.delete_cookie(key="session_id", path="/")

        return response

    @get("/me")
    async def get_current_user(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
    ) -> UserResponse:
        """Get current authenticated user."""
        user: AuthenticatedUser | None = request.scope.get("user")

        if not user:
            raise NotAuthorizedException(detail="Not authenticated")

        return UserResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            capabilities=sorted(user.capabilities),
        )

    async def _get_user_capabilities(
        self, conn: psycopg.AsyncConnection, user_id: str
    ) -> list[str]:
        """Get all capabilities for a user through their roles."""
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_capabilities(),
                {"user_id": user_id},
            )
            rows = await cur.fetchall()

        return [row[0] for row in rows]
