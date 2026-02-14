from dataclasses import dataclass
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException
from litestar.params import Parameter

import core.db as db
from core.guards import require_capability
from core.password import hash_password
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_users_search() -> str:
    """Search for users by username or full name."""
    return """
        SELECT id, username, full_name
        FROM users
        WHERE
            NOT inactive
            AND (
                username ILIKE %(pattern)s
                OR full_name ILIKE %(pattern)s
            )
        ORDER BY full_name, username
        LIMIT 10
    """


def sql_select_users() -> str:
    """List all users."""
    return """
        SELECT id, username, full_name, descr, inactive
        FROM users
        ORDER BY inactive, username
    """


def sql_select_user_by_id() -> str:
    """Get a single user by ID."""
    return """
        SELECT id, username, full_name, descr, inactive
        FROM users
        WHERE id = %(id)s
    """


def sql_select_user_exists() -> str:
    """Check if a user exists."""
    return "SELECT id FROM users WHERE id = %(id)s"


def sql_select_user_roles() -> str:
    """Get all roles with assigned status for a user."""
    return """
        SELECT
            r.id,
            r.role_name,
            CASE WHEN ur.userid IS NOT NULL THEN true ELSE false END AS assigned
        FROM roles r
        LEFT JOIN userroles ur
            ON ur.roleid = r.id
            AND ur.userid = %(user_id)s
        ORDER BY r.sort, r.role_name
    """


def sql_insert_user() -> str:
    """Create a new user."""
    return """
        INSERT INTO users (username, full_name, descr)
        VALUES (%(username)s, %(full_name)s, %(descr)s)
        RETURNING id, username, full_name, descr, inactive
    """


def sql_insert_user_role() -> str:
    """Add a role to a user (idempotent)."""
    return """
        INSERT INTO userroles (userid, roleid)
        VALUES (%(user_id)s, %(role_id)s)
        ON CONFLICT (userid, roleid) DO NOTHING
    """


def sql_update_user(fields: set[str]) -> str:
    """Update user fields dynamically."""
    valid_fields = {"username", "full_name", "descr", "inactive"}
    updates = [f"{f} = %({f})s" for f in fields if f in valid_fields]
    if not updates:
        raise ValueError("No valid fields to update")
    return f"""
        UPDATE users
        SET {", ".join(updates)}
        WHERE id = %(id)s
        RETURNING id, username, full_name, descr, inactive
    """


def sql_update_user_password() -> str:
    """Update a user's password hash."""
    return "UPDATE users SET pwhash = %(pwhash)s WHERE id = %(id)s"


def sql_update_user_inactive() -> str:
    """Soft-delete a user by setting inactive=true."""
    return "UPDATE users SET inactive = true WHERE id = %(id)s"


def sql_delete_user_role() -> str:
    """Remove a role from a user."""
    return """
        DELETE FROM userroles
        WHERE userid = %(user_id)s AND roleid = %(role_id)s
    """


# User columns
USER_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="username", label="Username", type="string"),
    ColumnMeta(key="full_name", label="Full Name", type="string"),
    ColumnMeta(key="descr", label="Description", type="string"),
    ColumnMeta(key="inactive", label="Inactive", type="boolean"),
]

# User role columns (for GET /users/{id}/roles)
USER_ROLE_COLUMNS = [
    ColumnMeta(key="role", label="Role", type="ref"),
    ColumnMeta(key="assigned", label="Assigned", type="boolean"),
]


@dataclass
class UserCreate:
    username: str
    full_name: str | None = None
    descr: str | None = None


@dataclass
class UserUpdate:
    username: str | None = None
    full_name: str | None = None
    descr: str | None = None
    inactive: bool | None = None


@dataclass
class UserRoleUpdate:
    role_id: str
    assigned: bool


@dataclass
class PasswordUpdate:
    password: str


async def _get_user_by_id(
    conn: psycopg.AsyncConnection, user_id: UUID
) -> SingleRowResponse:
    """Get a single user by ID."""
    return await db.select_one(
        conn,
        sql_select_user_by_id(),
        {"id": user_id},
        columns=USER_COLUMNS,
    )


class UsersController(Controller):
    path = "/api/users"
    tags = ["users"]

    @get("/search", guards=[require_capability("contacts:write")])
    async def search_users(
        self,
        conn: psycopg.AsyncConnection,
        q: str = Parameter(description="Search query", min_length=1),
    ) -> MultiRowResponse:
        """Search for users by username or full name.

        Used for contact sharing. Requires contacts:write capability.
        """
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_users_search(),
                {"pattern": f"%{q}%"},
            )
            rows = await cur.fetchall()

        columns = [
            ColumnMeta(key="id", label="ID", type="uuid"),
            ColumnMeta(key="username", label="Username", type="string"),
            ColumnMeta(key="full_name", label="Full Name", type="string"),
        ]
        return MultiRowResponse(columns=columns, data=[dict(row) for row in rows])

    @get(guards=[require_capability("admin:users")])
    async def list_users(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all users."""
        return await db.select_many(
            conn,
            sql_select_users(),
            columns=USER_COLUMNS,
        )

    @get("/{user_id:uuid}", guards=[require_capability("admin:users")])
    async def get_user(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
    ) -> SingleRowResponse:
        """Get a single user by ID."""
        return await _get_user_by_id(conn, user_id)

    @post(status_code=201, guards=[require_capability("admin:users")])
    async def create_user(
        self,
        conn: psycopg.AsyncConnection,
        data: UserCreate,
    ) -> SingleRowResponse:
        """Create a new user."""
        result = await db.execute_returning(
            conn,
            sql_insert_user(),
            {
                "username": data.username,
                "full_name": data.full_name,
                "descr": data.descr,
            },
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create user")
        return SingleRowResponse(columns=USER_COLUMNS, data=result)

    @put("/{user_id:uuid}", guards=[require_capability("admin:users")])
    async def update_user(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
        data: UserUpdate,
    ) -> SingleRowResponse:
        """Update an existing user."""
        fields: set[str] = set()
        params: dict[str, str | bool | UUID | None] = {"id": user_id}

        if data.username is not None:
            fields.add("username")
            params["username"] = data.username
        if data.full_name is not None:
            fields.add("full_name")
            params["full_name"] = data.full_name
        if data.descr is not None:
            fields.add("descr")
            params["descr"] = data.descr
        if data.inactive is not None:
            fields.add("inactive")
            params["inactive"] = data.inactive

        if not fields:
            return await _get_user_by_id(conn, user_id)

        row = await db.execute_returning(
            conn,
            sql_update_user(fields),
            params,
        )
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return SingleRowResponse(columns=USER_COLUMNS, data=row)

    @delete("/{user_id:uuid}", status_code=204, guards=[require_capability("admin:users")])
    async def delete_user(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
    ) -> None:
        """Soft-delete a user by setting inactive=true."""
        count = await db.execute(
            conn,
            sql_update_user_inactive(),
            {"id": user_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="User not found")

    @get("/{user_id:uuid}/roles", guards=[require_capability("admin:users")])
    async def get_user_roles(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
    ) -> MultiRowResponse:
        """Get all roles with assigned status for a user."""
        # First verify user exists
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_exists(),
                {"id": user_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

        # Get all roles with assigned flag for this user
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_roles(),
                {"user_id": user_id},
            )
            rows = await cur.fetchall()

        data = [
            {
                "role": {"id": str(row[0]), "name": row[1]},
                "assigned": row[2],
            }
            for row in rows
        ]

        return MultiRowResponse(columns=USER_ROLE_COLUMNS, data=data)

    @put("/{user_id:uuid}/roles", guards=[require_capability("admin:users")])
    async def update_user_roles(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
        data: list[UserRoleUpdate],
    ) -> MultiRowResponse:
        """Bulk update user role assignments."""
        # Verify user exists
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_exists(),
                {"id": user_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

        # Process each role update
        async with conn.cursor() as cur:
            for update in data:
                role_id = update.role_id
                if update.assigned:
                    # Add mapping if not exists
                    await cur.execute(
                        sql_insert_user_role(),
                        {"user_id": user_id, "role_id": role_id},
                    )
                else:
                    # Remove mapping
                    await cur.execute(
                        sql_delete_user_role(),
                        {"user_id": user_id, "role_id": role_id},
                    )

        # Return updated state - fetch roles with assigned status
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_user_roles(),
                {"user_id": user_id},
            )
            role_rows = await cur.fetchall()

        role_data: list[dict[str, object]] = [
            {
                "role": {"id": str(row[0]), "name": row[1]},
                "assigned": row[2],
            }
            for row in role_rows
        ]

        return MultiRowResponse(columns=USER_ROLE_COLUMNS, data=role_data)

    @put("/{user_id:uuid}/password", status_code=204, guards=[require_capability("admin:users")])
    async def set_password(
        self,
        conn: psycopg.AsyncConnection,
        user_id: UUID,
        data: PasswordUpdate,
    ) -> None:
        """Set or update a user's password."""
        if not data.password:
            raise HTTPException(status_code=400, detail="Password cannot be empty")

        pwhash = hash_password(data.password)

        count = await db.execute(
            conn,
            sql_update_user_password(),
            {"id": user_id, "pwhash": pwhash},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="User not found")
