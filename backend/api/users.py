from dataclasses import dataclass
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException

import core.db as db
from core.guards import require_capability
from core.password import hash_password
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


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
        """
        SELECT id, username, full_name, descr, inactive
        FROM users
        WHERE id = %(id)s
        """,
        {"id": user_id},
        columns=USER_COLUMNS,
    )


class UsersController(Controller):
    path = "/api/users"
    tags = ["users"]

    @get(guards=[require_capability("admin:users")])
    async def list_users(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all users."""
        return await db.select_many(
            conn,
            """
            SELECT id, username, full_name, descr, inactive
            FROM users
            ORDER BY inactive, username
            """,
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
            """
            INSERT INTO users (username, full_name, descr)
            VALUES (%(username)s, %(full_name)s, %(descr)s)
            RETURNING id, username, full_name, descr, inactive
            """,
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
        updates = []
        params: dict[str, str | bool | UUID | None] = {"id": user_id}

        if data.username is not None:
            updates.append("username = %(username)s")
            params["username"] = data.username
        if data.full_name is not None:
            updates.append("full_name = %(full_name)s")
            params["full_name"] = data.full_name
        if data.descr is not None:
            updates.append("descr = %(descr)s")
            params["descr"] = data.descr
        if data.inactive is not None:
            updates.append("inactive = %(inactive)s")
            params["inactive"] = data.inactive

        if not updates:
            return await _get_user_by_id(conn, user_id)

        row = await db.execute_returning(
            conn,
            f"""
            UPDATE users
            SET {", ".join(updates)}
            WHERE id = %(id)s
            RETURNING id, username, full_name, descr, inactive
            """,
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
            "UPDATE users SET inactive = true WHERE id = %(id)s",
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
                "SELECT id FROM users WHERE id = %(id)s",
                {"id": user_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

        # Get all roles with assigned flag for this user
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    r.id,
                    r.role_name,
                    CASE WHEN ur.userid IS NOT NULL THEN true ELSE false END AS assigned
                FROM roles r
                LEFT JOIN userroles ur
                    ON ur.roleid = r.id
                    AND ur.userid = %(user_id)s
                ORDER BY r.sort, r.role_name
                """,
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
                "SELECT id FROM users WHERE id = %(id)s",
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
                        """
                        INSERT INTO userroles (userid, roleid)
                        VALUES (%(user_id)s, %(role_id)s)
                        ON CONFLICT (userid, roleid) DO NOTHING
                        """,
                        {"user_id": user_id, "role_id": role_id},
                    )
                else:
                    # Remove mapping
                    await cur.execute(
                        """
                        DELETE FROM userroles
                        WHERE userid = %(user_id)s AND roleid = %(role_id)s
                        """,
                        {"user_id": user_id, "role_id": role_id},
                    )

        # Return updated state - fetch roles with assigned status
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    r.id,
                    r.role_name,
                    CASE WHEN ur.userid IS NOT NULL THEN true ELSE false END AS assigned
                FROM roles r
                LEFT JOIN userroles ur
                    ON ur.roleid = r.id
                    AND ur.userid = %(user_id)s
                ORDER BY r.sort, r.role_name
                """,
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
            "UPDATE users SET pwhash = %(pwhash)s WHERE id = %(id)s",
            {"id": user_id, "pwhash": pwhash},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="User not found")
