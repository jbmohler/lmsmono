from dataclasses import dataclass
from uuid import UUID

import psycopg
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException

import core.db as db
from core.guards import require_capability
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_journals() -> str:
    """List all journals."""
    return """
        SELECT id, jrn_name, description
        FROM hacc.journals
        ORDER BY jrn_name
    """


def sql_select_journal_by_id() -> str:
    """Get a single journal by ID."""
    return """
        SELECT id, jrn_name, description
        FROM hacc.journals
        WHERE id = %(id)s
    """


def sql_select_journal_accounts_count() -> str:
    """Count accounts using a journal (for delete check)."""
    return """
        SELECT COUNT(*) FROM hacc.accounts
        WHERE journal_id = %(id)s
    """


def sql_insert_journal() -> str:
    """Create a new journal."""
    return """
        INSERT INTO hacc.journals (jrn_name, description)
        VALUES (%(jrn_name)s, %(description)s)
        RETURNING id, jrn_name, description
    """


def sql_update_journal(fields: set[str]) -> str:
    """Update journal fields dynamically."""
    valid_fields = {"jrn_name", "description"}
    updates = [f"{f} = %({f})s" for f in fields if f in valid_fields]
    if not updates:
        raise ValueError("No valid fields to update")
    return f"""
        UPDATE hacc.journals
        SET {", ".join(updates)}
        WHERE id = %(id)s
        RETURNING id, jrn_name, description
    """


def sql_delete_journal() -> str:
    """Delete a journal by ID."""
    return "DELETE FROM hacc.journals WHERE id = %(id)s"


JOURNAL_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="jrn_name", label="Name", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
]


@dataclass
class JournalCreate:
    jrn_name: str
    description: str | None = None


@dataclass
class JournalUpdate:
    jrn_name: str | None = None
    description: str | None = None


async def _get_journal_by_id(
    conn: psycopg.AsyncConnection, journal_id: UUID
) -> SingleRowResponse:
    """Get a single journal by ID (shared logic)."""
    return await db.select_one(
        conn,
        sql_select_journal_by_id(),
        {"id": journal_id},
        columns=JOURNAL_COLUMNS,
    )


class JournalsController(Controller):
    path = "/api/journals"
    tags = ["journals"]

    @get(guards=[require_capability("journals:read")])
    async def list_journals(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List all journals."""
        return await db.select_many(
            conn,
            sql_select_journals(),
            columns=JOURNAL_COLUMNS,
        )

    @get("/{journal_id:uuid}", guards=[require_capability("journals:read")])
    async def get_journal(
        self,
        conn: psycopg.AsyncConnection,
        journal_id: UUID,
    ) -> SingleRowResponse:
        """Get a single journal by ID."""
        return await _get_journal_by_id(conn, journal_id)

    @post(status_code=201, guards=[require_capability("journals:write")])
    async def create_journal(
        self,
        conn: psycopg.AsyncConnection,
        data: JournalCreate,
    ) -> SingleRowResponse:
        """Create a new journal."""
        row = await db.execute_returning(
            conn,
            sql_insert_journal(),
            {"jrn_name": data.jrn_name, "description": data.description},
        )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create journal")
        return SingleRowResponse(columns=JOURNAL_COLUMNS, data=row)

    @put("/{journal_id:uuid}", guards=[require_capability("journals:write")])
    async def update_journal(
        self,
        conn: psycopg.AsyncConnection,
        journal_id: UUID,
        data: JournalUpdate,
    ) -> SingleRowResponse:
        """Update an existing journal."""
        # Build dynamic update query
        fields: set[str] = set()
        params: dict[str, str | UUID | None] = {"id": journal_id}
        if data.jrn_name is not None:
            fields.add("jrn_name")
            params["jrn_name"] = data.jrn_name
        if data.description is not None:
            fields.add("description")
            params["description"] = data.description

        if not fields:
            # No updates, just return current state
            return await _get_journal_by_id(conn, journal_id)

        row = await db.execute_returning(
            conn,
            sql_update_journal(fields),
            params,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Journal not found")
        return SingleRowResponse(columns=JOURNAL_COLUMNS, data=row)

    @delete("/{journal_id:uuid}", status_code=204, guards=[require_capability("journals:write")])
    async def delete_journal(
        self,
        conn: psycopg.AsyncConnection,
        journal_id: UUID,
    ) -> None:
        """Delete a journal. Only succeeds if no accounts reference it."""
        # Check if any accounts use this journal
        async with conn.cursor() as cur:
            await cur.execute(
                sql_select_journal_accounts_count(),
                {"id": journal_id},
            )
            row = await cur.fetchone()
            if row and row[0] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot delete journal: accounts are using it",
                )

        count = await db.execute(
            conn,
            sql_delete_journal(),
            {"id": journal_id},
        )
        if count == 0:
            raise HTTPException(status_code=404, detail="Journal not found")
