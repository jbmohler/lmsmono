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

async def _get_bit_by_id(
    conn: psycopg.AsyncConnection, bit_id: UUID
) -> SingleRowResponse:
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(sql_select_bit_by_id(), {"id": bit_id})
        row = await cur.fetchone()
    if not row:
        raise NotFoundException(detail="Data bit not found")
    return SingleRowResponse(columns=DATABIT_DETAIL_COLUMNS, data=dict(row))


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
