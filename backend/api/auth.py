"""Authentication controller for login, logout, and session management."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import traceback

import jwt
import psycopg
from litestar import Controller, Request, Response, get, post
from litestar.exceptions import NotAuthorizedException, ValidationException

from core.auth import AuthenticatedUser
from core.email import send_password_reset_email
from core.jwt_utils import create_reset_token, decode_reset_token
from core.password import hash_password, verify_password
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


def sql_select_user_primary_email() -> str:
    """Get a user's primary email address, falling back to any email."""
    return """
        SELECT u.id, u.username, a.address
        FROM users u
        LEFT JOIN addresses a
            ON a.userid = u.id
            AND a.addr_type = 'email'
        WHERE u.username = %(username)s
          AND u.inactive = false
        ORDER BY a.is_primary DESC NULLS LAST
        LIMIT 1
    """


def sql_update_user_password() -> str:
    """Update a user's password hash."""
    return "UPDATE users SET pwhash = %(pwhash)s WHERE id = %(id)s"


@dataclass
class LoginRequest:
    username: str
    password: str


@dataclass
class ForgotPasswordRequest:
    username: str


@dataclass
class ResetPasswordRequest:
    token: str
    new_password: str


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
                {"username": data.username.strip().lower()},
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

    @post("/forgot-password", status_code=200)
    async def forgot_password(
        self,
        conn: psycopg.AsyncConnection,
        data: ForgotPasswordRequest,
    ) -> dict:
        """Send a password reset email.

        Always returns 200 to avoid revealing whether a username exists.
        """
        config = _get_config()

        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_primary_email(),
                {"username": data.username.strip().lower()},
            )
            row = await cur.fetchone()

        if not row:
            # Return success silently - don't reveal if username exists
            return {"ok": True}

        user_id, username, email_address = row

        if not email_address:
            print(f"Password reset requested for user {username} but no email on file")
            return {"ok": True}

        token = create_reset_token(str(user_id), config.session.secret_key)
        reset_url = f"{config.app_base_url}/reset-password?token={token}"

        try:
            send_password_reset_email(config.smtp, email_address, username, reset_url)
        except Exception:
            print(f"Failed to send password reset email to {email_address}")
            print(traceback.format_exc())

        return {"ok": True}

    @post("/reset-password", status_code=200)
    async def reset_password(
        self,
        conn: psycopg.AsyncConnection,
        data: ResetPasswordRequest,
    ) -> dict:
        """Reset a user's password using a valid reset token."""
        config = _get_config()

        if not data.new_password or len(data.new_password) < 8:
            raise ValidationException("Password must be at least 8 characters")

        try:
            user_id = decode_reset_token(data.token, config.session.secret_key)
        except jwt.ExpiredSignatureError:
            raise ValidationException("Reset link has expired")
        except jwt.InvalidTokenError:
            raise ValidationException("Invalid reset token")

        async with conn.cursor() as cur:
            await cur.execute(
                sql_update_user_password(),
                {"id": user_id, "pwhash": hash_password(data.new_password)},
            )

        return {"ok": True}

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
