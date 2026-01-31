from dataclasses import dataclass
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


# Capability columns
CAPABILITY_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="cap_name", label="Name", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
]

# Role columns
ROLE_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="role_name", label="Name", type="string"),
    ColumnMeta(key="sort", label="Sort", type="number"),
]

# Role capability columns (for GET /roles/{id}/capabilities)
ROLE_CAPABILITY_COLUMNS = [
    ColumnMeta(key="capability", label="Capability", type="ref"),
    ColumnMeta(key="permitted", label="Permitted", type="boolean"),
]


@dataclass
class RoleCreate:
    role_name: str
    sort: int | None = None


@dataclass
class RoleUpdate:
    role_name: str | None = None
    sort: int | None = None


@dataclass
class RoleCapabilityUpdate:
    capability_id: str
    permitted: bool


async def _get_role_by_id(
    conn: psycopg.AsyncConnection, role_id: UUID
) -> SingleRowResponse:
    """Get a single role by ID."""
    return await db.select_one(
        conn,
        """
        SELECT id, role_name, sort
        FROM roles
        WHERE id = %(id)s
        """,
        {"id": role_id},
        columns=ROLE_COLUMNS,
    )


class CapabilitiesController(Controller):
    path = "/api/capabilities"
    tags = ["capabilities"]

    @get()
    async def list_capabilities(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all capabilities."""
        return await db.select_many(
            conn,
            """
            SELECT id, cap_name, description
            FROM capabilities
            ORDER BY cap_name
            """,
            columns=CAPABILITY_COLUMNS,
        )


class RolesController(Controller):
    path = "/api/roles"
    tags = ["roles"]

    @get()
    async def list_roles(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all roles."""
        return await db.select_many(
            conn,
            """
            SELECT id, role_name, sort
            FROM roles
            ORDER BY sort, role_name
            """,
            columns=ROLE_COLUMNS,
        )

    @get("/{role_id:uuid}")
    async def get_role(
        self,
        conn: psycopg.AsyncConnection,
        role_id: UUID,
    ) -> SingleRowResponse:
        """Get a single role by ID."""
        return await _get_role_by_id(conn, role_id)

    @post(status_code=201)
    async def create_role(
        self,
        conn: psycopg.AsyncConnection,
        data: RoleCreate,
    ) -> SingleRowResponse:
        """Create a new role."""
        # Get max sort value if not provided
        sort_value = data.sort
        if sort_value is None:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COALESCE(MAX(sort), 0) + 1 FROM roles")
                max_row = await cur.fetchone()
                sort_value = max_row[0] if max_row else 1

        result = await db.execute_returning(
            conn,
            """
            INSERT INTO roles (role_name, sort)
            VALUES (%(role_name)s, %(sort)s)
            RETURNING id, role_name, sort
            """,
            {"role_name": data.role_name, "sort": sort_value},
        )
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create role")
        return SingleRowResponse(columns=ROLE_COLUMNS, data=result)

    @put("/{role_id:uuid}")
    async def update_role(
        self,
        conn: psycopg.AsyncConnection,
        role_id: UUID,
        data: RoleUpdate,
    ) -> SingleRowResponse:
        """Update an existing role."""
        updates = []
        params: dict[str, str | int | UUID | None] = {"id": role_id}
        if data.role_name is not None:
            updates.append("role_name = %(role_name)s")
            params["role_name"] = data.role_name
        if data.sort is not None:
            updates.append("sort = %(sort)s")
            params["sort"] = data.sort

        if not updates:
            return await _get_role_by_id(conn, role_id)

        row = await db.execute_returning(
            conn,
            f"""
            UPDATE roles
            SET {", ".join(updates)}
            WHERE id = %(id)s
            RETURNING id, role_name, sort
            """,
            params,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Role not found")
        return SingleRowResponse(columns=ROLE_COLUMNS, data=row)

    @delete("/{role_id:uuid}", status_code=204)
    async def delete_role(
        self,
        conn: psycopg.AsyncConnection,
        role_id: UUID,
    ) -> None:
        """Delete a role."""
        # First delete role-capability mappings
        await db.execute(
            conn,
            "DELETE FROM rolecapabilities WHERE roleid = %(role_id)s",
            {"role_id": role_id},
        )

        count = await db.execute(
            conn,
            "DELETE FROM roles WHERE id = %(id)s",
            {"id": role_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Role not found")

    @get("/{role_id:uuid}/capabilities")
    async def get_role_capabilities(
        self,
        conn: psycopg.AsyncConnection,
        role_id: UUID,
    ) -> MultiRowResponse:
        """Get all capabilities with permitted status for a role."""
        # First verify role exists
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM roles WHERE id = %(id)s",
                {"id": role_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

        # Get all capabilities with permitted flag for this role
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    c.id,
                    c.cap_name,
                    CASE WHEN rc.roleid IS NOT NULL THEN true ELSE false END AS permitted
                FROM capabilities c
                LEFT JOIN rolecapabilities rc
                    ON rc.capabilityid = c.id
                    AND rc.roleid = %(role_id)s
                ORDER BY c.cap_name
                """,
                {"role_id": role_id},
            )
            rows = await cur.fetchall()

        data = [
            {
                "capability": {"id": str(row[0]), "name": row[1]},
                "permitted": row[2],
            }
            for row in rows
        ]

        return MultiRowResponse(columns=ROLE_CAPABILITY_COLUMNS, data=data)

    @put("/{role_id:uuid}/capabilities")
    async def update_role_capabilities(
        self,
        conn: psycopg.AsyncConnection,
        role_id: UUID,
        data: list[RoleCapabilityUpdate],
    ) -> MultiRowResponse:
        """Bulk update role capabilities."""
        # Verify role exists
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id FROM roles WHERE id = %(id)s",
                {"id": role_id},
            )
            if not await cur.fetchone():
                raise HTTPException(status_code=404, detail="Role not found")

        # Process each capability update
        async with conn.cursor() as cur:
            for update in data:
                cap_id = update.capability_id
                if update.permitted:
                    # Add mapping if not exists
                    await cur.execute(
                        """
                        INSERT INTO rolecapabilities (roleid, capabilityid)
                        VALUES (%(role_id)s, %(cap_id)s)
                        ON CONFLICT (roleid, capabilityid) DO NOTHING
                        """,
                        {"role_id": role_id, "cap_id": cap_id},
                    )
                else:
                    # Remove mapping
                    await cur.execute(
                        """
                        DELETE FROM rolecapabilities
                        WHERE roleid = %(role_id)s AND capabilityid = %(cap_id)s
                        """,
                        {"role_id": role_id, "cap_id": cap_id},
                    )

        # Return updated state - fetch capabilities with permitted status
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT
                    c.id,
                    c.cap_name,
                    CASE WHEN rc.roleid IS NOT NULL THEN true ELSE false END AS permitted
                FROM capabilities c
                LEFT JOIN rolecapabilities rc
                    ON rc.capabilityid = c.id
                    AND rc.roleid = %(role_id)s
                ORDER BY c.cap_name
                """,
                {"role_id": role_id},
            )
            cap_rows = await cur.fetchall()

        cap_data: list[dict[str, object]] = [
            {
                "capability": {"id": str(row[0]), "name": row[1]},
                "permitted": row[2],
            }
            for row in cap_rows
        ]

        return MultiRowResponse(columns=ROLE_CAPABILITY_COLUMNS, data=cap_data)
