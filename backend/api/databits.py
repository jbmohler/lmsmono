from dataclasses import dataclass
from uuid import UUID

import psycopg
import psycopg.rows
from litestar import Controller, delete, get, post, put
from litestar.exceptions import HTTPException, NotFoundException
from litestar.params import Parameter

import core.db as db
from core.auth import AuthenticatedUser
from core.guards import require_capability
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------


def sql_select_bits() -> str:
    return """
        SELECT
            b.id,
            b.caption,
            b.website,
            b.uname
        FROM databits.bits b
        JOIN databits.perfts_search p ON p.id = b.id
        WHERE (
            %(search)s::text IS NULL
            OR p.fts_search @@ websearch_to_tsquery('simple', %(search)s)
            OR p.fts_search @@ websearch_to_tsquery('english', %(search)s)
            OR p.fts_search @@ to_tsquery('simple',
                (SELECT string_agg(lexeme || ':*', ' & ')
                 FROM unnest(to_tsvector('simple', %(search)s)))
            )
        )
        ORDER BY b.caption
        LIMIT %(limit)s OFFSET %(offset)s
    """


def sql_select_bit_by_id() -> str:
    return """
        SELECT
            id,
            caption,
            data,
            website,
            uname,
            pword
        FROM databits.bits
        WHERE id = %(id)s
    """


def sql_insert_bit() -> str:
    return """
        INSERT INTO databits.bits (caption, data, website, uname, pword)
        VALUES (%(caption)s, %(data)s, %(website)s, %(uname)s, %(pword)s)
        RETURNING id
    """


def sql_update_bit(fields: set[str]) -> str:
    field_map = {"caption": "caption", "data": "data", "website": "website",
                 "uname": "uname", "pword": "pword"}
    updates = [f"{field_map[f]} = %({f})s" for f in fields if f in field_map]
    if not updates:
        raise ValueError("No valid fields to update")
    return f"UPDATE databits.bits SET {', '.join(updates)} WHERE id = %(id)s"


def sql_delete_bit() -> str:
    return "DELETE FROM databits.bits WHERE id = %(id)s"


def sql_select_all_databit_tags() -> str:
    return """
        SELECT id, name, description
        FROM databits.tags
        ORDER BY name
    """


def sql_select_bit_tags() -> str:
    return """
        SELECT t.id, t.name, t.description
        FROM databits.tagbits tb
        JOIN databits.tags t ON t.id = tb.tag_id
        WHERE tb.bit_id = %(bit_id)s
        ORDER BY t.name
    """


def sql_insert_bit_tag() -> str:
    return """
        INSERT INTO databits.tagbits (tag_id, bit_id)
        VALUES (%(tag_id)s, %(bit_id)s)
        ON CONFLICT DO NOTHING
    """


def sql_delete_bit_tag() -> str:
    return """
        DELETE FROM databits.tagbits
        WHERE bit_id = %(bit_id)s AND tag_id = %(tag_id)s
    """


# ---------------------------------------------------------------------------
# Column definitions
# ---------------------------------------------------------------------------

DATABIT_LIST_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="caption", label="Caption", type="string"),
    ColumnMeta(key="website", label="Website", type="string"),
    ColumnMeta(key="uname", label="Username", type="string"),
]

DATABIT_DETAIL_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="caption", label="Caption", type="string"),
    ColumnMeta(key="data", label="Notes", type="string"),
    ColumnMeta(key="website", label="Website", type="string"),
    ColumnMeta(key="uname", label="Username", type="string"),
    ColumnMeta(key="tags", label="Tags", type="array"),
]

DATABIT_TAG_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="name", label="Name", type="string"),
    ColumnMeta(key="description", label="Description", type="string"),
]


# ---------------------------------------------------------------------------
# Request dataclasses
# ---------------------------------------------------------------------------

@dataclass
class DataBitCreate:
    caption: str | None = None
    data: str | None = None
    website: str | None = None
    uname: str | None = None
    pword: str | None = None


@dataclass
class DataBitUpdate:
    caption: str | None = None
    data: str | None = None
    website: str | None = None
    uname: str | None = None
    pword: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tags_for_bit(
    conn: psycopg.AsyncConnection, bit_id: UUID
) -> list[dict]:
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(sql_select_bit_tags(), {"bit_id": bit_id})
        rows = await cur.fetchall()
    return [
        {"id": str(row["id"]), "name": row["name"], "description": row["description"] or ""}
        for row in rows
    ]


async def _get_bit_by_id(
    conn: psycopg.AsyncConnection, bit_id: UUID
) -> SingleRowResponse:
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(sql_select_bit_by_id(), {"id": bit_id})
        row = await cur.fetchone()
    if not row:
        raise NotFoundException(detail="Data bit not found")
    data = dict(row)
    data["tags"] = await _get_tags_for_bit(conn, bit_id)
    return SingleRowResponse(columns=DATABIT_DETAIL_COLUMNS, data=data)


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class DataBitsController(Controller):
    path = "/api/databits"
    tags = ["databits"]

    @get(guards=[require_capability("databits:read")])
    async def list_bits(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        search: str | None = Parameter(default=None, description="Search query"),
        limit: int = Parameter(default=50, le=500, ge=1),
        offset: int = Parameter(default=0, ge=0),
    ) -> MultiRowResponse:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_select_bits(),
                {"search": search, "limit": limit, "offset": offset},
            )
            rows = await cur.fetchall()
        return MultiRowResponse(
            columns=DATABIT_LIST_COLUMNS,
            data=[dict(row) for row in rows],
        )

    @get("/{bit_id:uuid}", guards=[require_capability("databits:read")])
    async def get_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        bit_id: UUID,
    ) -> SingleRowResponse:
        return await _get_bit_by_id(conn, bit_id)

    @post(status_code=201, guards=[require_capability("databits:write")])
    async def create_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        data: DataBitCreate,
    ) -> SingleRowResponse:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(
                sql_insert_bit(),
                {
                    "caption": data.caption,
                    "data": data.data,
                    "website": data.website,
                    "uname": data.uname,
                    "pword": data.pword,
                },
            )
            row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create data bit")
        return await _get_bit_by_id(conn, row["id"])

    @put("/{bit_id:uuid}", guards=[require_capability("databits:write")])
    async def update_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        bit_id: UUID,
        data: DataBitUpdate,
    ) -> SingleRowResponse:
        fields: set[str] = set()
        params: dict = {"id": bit_id}

        if data.caption is not None:
            fields.add("caption")
            params["caption"] = data.caption
        if data.data is not None:
            fields.add("data")
            params["data"] = data.data
        if data.website is not None:
            fields.add("website")
            params["website"] = data.website
        if data.uname is not None:
            fields.add("uname")
            params["uname"] = data.uname
        if data.pword is not None:
            fields.add("pword")
            params["pword"] = data.pword

        if not fields:
            return await _get_bit_by_id(conn, bit_id)

        count = await db.execute(conn, sql_update_bit(fields), params)
        if count == 0:
            raise NotFoundException(detail="Data bit not found")

        return await _get_bit_by_id(conn, bit_id)

    @delete("/{bit_id:uuid}", status_code=204, guards=[require_capability("databits:write")])
    async def delete_bit(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        bit_id: UUID,
    ) -> None:
        count = await db.execute(conn, sql_delete_bit(), {"id": bit_id})
        if count == 0:
            raise NotFoundException(detail="Data bit not found")

    # -------------------------------------------------------------------------
    # Tag Endpoints
    # -------------------------------------------------------------------------

    @get("/tags", guards=[require_capability("databits:read")])
    async def list_databit_tags(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
    ) -> MultiRowResponse:
        """Return all available databit tags."""
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(sql_select_all_databit_tags())
            rows = await cur.fetchall()
        return MultiRowResponse(
            columns=DATABIT_TAG_COLUMNS,
            data=[
                {"id": str(r["id"]), "name": r["name"], "description": r["description"] or ""}
                for r in rows
            ],
        )

    @post("/{bit_id:uuid}/tags/{tag_id:uuid}", status_code=200, guards=[require_capability("databits:write")])
    async def add_bit_tag(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        bit_id: UUID,
        tag_id: UUID,
    ) -> MultiRowResponse:
        """Add a tag to a data bit."""
        # Verify the bit exists
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM databits.bits WHERE id = %(id)s", {"id": bit_id})
            if not await cur.fetchone():
                raise NotFoundException(detail="Data bit not found")

        # Verify the tag exists
        async with conn.cursor() as cur:
            await cur.execute("SELECT id FROM databits.tags WHERE id = %(id)s", {"id": tag_id})
            if not await cur.fetchone():
                raise NotFoundException(detail="Tag not found")

        await db.execute(conn, sql_insert_bit_tag(), {"tag_id": tag_id, "bit_id": bit_id})

        tags = await _get_tags_for_bit(conn, bit_id)
        return MultiRowResponse(columns=DATABIT_TAG_COLUMNS, data=tags)

    @delete("/{bit_id:uuid}/tags/{tag_id:uuid}", status_code=200, guards=[require_capability("databits:write")])
    async def remove_bit_tag(
        self,
        conn: psycopg.AsyncConnection,
        current_user: AuthenticatedUser,
        bit_id: UUID,
        tag_id: UUID,
    ) -> MultiRowResponse:
        """Remove a tag from a data bit."""
        await db.execute(conn, sql_delete_bit_tag(), {"bit_id": bit_id, "tag_id": tag_id})

        tags = await _get_tags_for_bit(conn, bit_id)
        return MultiRowResponse(columns=DATABIT_TAG_COLUMNS, data=tags)
