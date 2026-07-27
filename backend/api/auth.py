"""Authentication controller for login, logout, and session management."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NoReturn
from uuid import uuid4

import traceback

import jwt
import psycopg
from litestar import Controller, Request, Response, get, post
from litestar.exceptions import NotAuthorizedException, ValidationException

import core.device_token as device_token
from core.auth import AuthenticatedUser, parse_session_id
from core.config import SessionConfig
from core.email import send_password_reset_email
from core.jwt_utils import create_reset_token, decode_reset_token
from core.password import hash_password, verify_dummy_password, verify_password
from core.queries_admin import sql_select_user_capabilities


# Every login failure returns this, regardless of cause. The specific reason is
# logged server-side only - distinct messages let an attacker enumerate users.
LOGIN_FAILED_DETAIL = "Invalid username or password"


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
    """Create a new session, optionally linked to a remember-me device token."""
    return """
        INSERT INTO sessions (id, userid, issued, expires, devtok_id)
        VALUES (%(id)s, %(userid)s, %(issued)s, %(expires)s, %(devtok_id)s)
    """


def sql_update_session_inactive() -> str:
    """Invalidate a session on logout."""
    return "UPDATE sessions SET inactive = true WHERE id = %(id)s"


def sql_insert_device_token() -> str:
    """Create a remember-me device token."""
    return """
        INSERT INTO devicetokens (id, userid, device_name, tokenhash, issued, expires)
        VALUES (%(id)s, %(userid)s, %(device_name)s, %(tokenhash)s, %(issued)s, %(expires)s)
    """


def sql_select_device_token() -> str:
    """Get a device token with its user for refresh validation."""
    return """
        SELECT
            dt.tokenhash,
            dt.expires,
            dt.inactive,
            u.id,
            u.username,
            u.full_name,
            u.inactive AS user_inactive
        FROM devicetokens dt
        JOIN users u ON u.id = dt.userid
        WHERE dt.id = %(id)s
    """


def sql_rotate_device_token() -> str:
    """Replace a device token's secret hash and slide its expiry forward."""
    return """
        UPDATE devicetokens
        SET tokenhash = %(tokenhash)s, expires = %(expires)s
        WHERE id = %(id)s
    """


def sql_update_device_token_inactive() -> str:
    """Invalidate a device token on logout."""
    return "UPDATE devicetokens SET inactive = true WHERE id = %(id)s"


def sql_update_all_sessions_inactive() -> str:
    """Invalidate every session belonging to a user (sign out everywhere)."""
    return "UPDATE sessions SET inactive = true WHERE userid = %(userid)s"


def sql_update_all_device_tokens_inactive() -> str:
    """Invalidate every device token belonging to a user (sign out everywhere)."""
    return "UPDATE devicetokens SET inactive = true WHERE userid = %(userid)s"


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
    remember: bool = False


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


def _reject_login(request: Request, username: str, reason: str) -> NoReturn:
    """Log why a login attempt failed, then raise the generic error."""
    client = request.scope.get("client")
    origin = client[0] if client else "unknown"
    print(f"Login failed from {origin} for username {username!r}: {reason}")
    raise NotAuthorizedException(detail=LOGIN_FAILED_DETAIL)


# The remember-me cookie is scoped to /api/auth so it is sent only to the
# refresh and logout endpoints, never to ordinary API calls.
REMEMBER_COOKIE_PATH = "/api/auth"


def _set_session_cookie(response: Response, session_id: str, cfg: SessionConfig) -> None:
    """Attach the short-lived session cookie to a response."""
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=cfg.secure_cookie,
        samesite="strict",
        path="/",
        max_age=cfg.expire_minutes * 60,
    )


def _set_remember_cookie(response: Response, value: str, cfg: SessionConfig) -> None:
    """Attach the long-lived remember-me cookie to a response."""
    response.set_cookie(
        key=cfg.remember_cookie_name,
        value=value,
        httponly=True,
        secure=cfg.secure_cookie,
        samesite="strict",
        path=REMEMBER_COOKIE_PATH,
        max_age=cfg.remember_days * 86400,
    )


async def _create_session(
    conn: psycopg.AsyncConnection,
    user_id: str,
    cfg: SessionConfig,
    devtok_id: str | None,
) -> str:
    """Insert a fresh session row and return its id."""
    session_id = str(uuid4())
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=cfg.expire_minutes)

    async with conn.cursor() as cur:
        await cur.execute(
            sql_insert_session(),
            {
                "id": session_id,
                "userid": user_id,
                "issued": now,
                "expires": expires,
                "devtok_id": devtok_id,
            },
        )

    return session_id


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

        attempted = data.username.strip().lower()

        # Look up user by username
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_by_username(),
                {"username": attempted},
            )
            row = await cur.fetchone()

        # Every failure path below burns exactly one Argon2 verify before
        # rejecting, so response timing does not distinguish the cause.
        if not row:
            verify_dummy_password(data.password)
            _reject_login(request, attempted, "no such user")

        user_id, username, full_name, pwhash, inactive = row

        if not pwhash:
            verify_dummy_password(data.password)
            _reject_login(request, attempted, "user has no password hash set")

        password_ok = verify_password(data.password, pwhash)

        if inactive:
            _reject_login(request, attempted, "account is inactive")

        if not password_ok:
            _reject_login(request, attempted, "password mismatch")

        # Get user capabilities
        capabilities = await self._get_user_capabilities(conn, user_id)

        # When "remember me" is requested, mint a long-lived device token first
        # so the session can be linked to it via devtok_id.
        devtok_id: str | None = None
        remember_cookie_value: str | None = None
        if data.remember:
            now = datetime.now(timezone.utc)
            minted = device_token.mint_token()
            async with conn.cursor() as cur:
                await cur.execute(
                    sql_insert_device_token(),
                    {
                        "id": minted.devtok_id,
                        "userid": user_id,
                        "device_name": request.headers.get("user-agent"),
                        "tokenhash": minted.tokenhash,
                        "issued": now,
                        "expires": now + timedelta(days=config.session.remember_days),
                    },
                )
            devtok_id = minted.devtok_id
            remember_cookie_value = minted.cookie_value

        session_id = await _create_session(conn, user_id, config.session, devtok_id)

        # Build response with cookie
        user_response = UserResponse(
            id=str(user_id),
            username=username,
            full_name=full_name,
            capabilities=sorted(capabilities),
        )

        response = Response(user_response)
        _set_session_cookie(response, session_id, config.session)
        if remember_cookie_value is not None:
            _set_remember_cookie(response, remember_cookie_value, config.session)

        return response

    @post("/refresh")
    async def refresh(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
    ) -> Response[UserResponse]:
        """Issue a fresh session from a valid remember-me device token.

        The device token secret is rotated on every use and its expiry slid
        forward, so an intercepted cookie is usable only until the next refresh
        and an active device stays signed in as long as it is used within the
        remember window. Every failure returns the same generic 401.
        """
        config = _get_config()

        parsed = device_token.split_cookie(
            request.cookies.get(config.session.remember_cookie_name)
        )
        if not parsed:
            raise NotAuthorizedException(detail="Not authenticated")

        devtok_id, secret = parsed

        async with conn.cursor() as cur:
            await cur.execute(sql_select_device_token(), {"id": devtok_id})
            row = await cur.fetchone()

        if not row:
            raise NotAuthorizedException(detail="Not authenticated")

        tokenhash, expires, inactive, user_id, username, full_name, user_inactive = row

        if inactive or user_inactive:
            raise NotAuthorizedException(detail="Not authenticated")

        # Column is timestamp without time zone but stores UTC (matches middleware).
        if expires and expires < datetime.now(timezone.utc).replace(tzinfo=None):
            raise NotAuthorizedException(detail="Not authenticated")

        if not device_token.verify_secret(secret, tokenhash):
            raise NotAuthorizedException(detail="Not authenticated")

        # Rotate the secret and slide the expiry forward for the same token id.
        now = datetime.now(timezone.utc)
        rotated = device_token.mint_token(devtok_id)
        async with conn.cursor() as cur:
            await cur.execute(
                sql_rotate_device_token(),
                {
                    "id": devtok_id,
                    "tokenhash": rotated.tokenhash,
                    "expires": now + timedelta(days=config.session.remember_days),
                },
            )

        capabilities = await self._get_user_capabilities(conn, user_id)
        session_id = await _create_session(conn, user_id, config.session, devtok_id)

        user_response = UserResponse(
            id=str(user_id),
            username=username,
            full_name=full_name,
            capabilities=sorted(capabilities),
        )

        response = Response(user_response)
        _set_session_cookie(response, session_id, config.session)
        _set_remember_cookie(response, rotated.cookie_value, config.session)

        return response

    @post("/logout")
    async def logout(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
    ) -> Response[dict]:
        """Invalidate the session and its device token, then clear both cookies."""
        config = _get_config()

        session_id = parse_session_id(request.cookies.get("session_id"))

        if session_id:
            async with conn.cursor() as cur:
                await cur.execute(
                    sql_update_session_inactive(),
                    {"id": session_id},
                )

        parsed = device_token.split_cookie(
            request.cookies.get(config.session.remember_cookie_name)
        )
        if parsed:
            devtok_id, _ = parsed
            async with conn.cursor() as cur:
                await cur.execute(
                    sql_update_device_token_inactive(),
                    {"id": devtok_id},
                )

        response = Response({"ok": True})
        response.delete_cookie(key="session_id", path="/")
        response.delete_cookie(
            key=config.session.remember_cookie_name, path=REMEMBER_COOKIE_PATH
        )

        return response

    @post("/logout-all")
    async def logout_all(
        self,
        conn: psycopg.AsyncConnection,
        request: Request,
    ) -> Response[dict]:
        """Sign out everywhere: invalidate every session and device token for
        the current user, then clear this browser's cookies.

        This is the remedy when a remember-me device is lost or a session may be
        compromised - it revokes all outstanding tokens, not just this one.
        """
        user: AuthenticatedUser | None = request.scope.get("user")
        if not user:
            raise NotAuthorizedException(detail="Not authenticated")

        config = _get_config()

        async with conn.cursor() as cur:
            await cur.execute(
                sql_update_all_sessions_inactive(), {"userid": user.id}
            )
            await cur.execute(
                sql_update_all_device_tokens_inactive(), {"userid": user.id}
            )

        response = Response({"ok": True})
        response.delete_cookie(key="session_id", path="/")
        response.delete_cookie(
            key=config.session.remember_cookie_name, path=REMEMBER_COOKIE_PATH
        )

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
