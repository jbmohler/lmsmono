from collections.abc import AsyncGenerator
from typing import Any

import psycopg
import psycopg.rows
import psycopg_pool
from litestar.exceptions import NotFoundException

from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


pool: psycopg_pool.AsyncConnectionPool | None = None


async def init_pool(conninfo: str) -> None:
    """Initialize the async connection pool."""
    global pool
    pool = psycopg_pool.AsyncConnectionPool(
        conninfo=conninfo,
        min_size=2,
        max_size=10,
        open=False,
    )
    await pool.open()
    await pool.wait()


async def close_pool() -> None:
    """Close the connection pool."""
    global pool
    if pool:
        await pool.close()
        pool = None


async def provide_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Litestar dependency provider for database connections."""
    if not pool:
        raise RuntimeError("Database pool not initialized")
    async with pool.connection() as conn:
        yield conn


async def select_one(
    conn: psycopg.AsyncConnection,
    query: str,
    params: dict[str, Any] | None = None,
    columns: list[ColumnMeta] | None = None,
) -> SingleRowResponse:
    """Execute query expecting exactly one row.

    Args:
        conn: Database connection
        query: SQL query with %(name)s style parameters
        params: Query parameters as dict
        columns: Column metadata for response

    Returns:
        SingleRowResponse with columns and data

    Raises:
        NotFoundException: If no row found
    """
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(query, params or {})
        row = await cur.fetchone()
        if not row:
            raise NotFoundException(detail="Not found")
        return SingleRowResponse(columns=columns or [], data=dict(row))


async def select_many(
    conn: psycopg.AsyncConnection,
    query: str,
    params: dict[str, Any] | None = None,
    columns: list[ColumnMeta] | None = None,
) -> MultiRowResponse:
    """Execute query returning multiple rows.

    Args:
        conn: Database connection
        query: SQL query with %(name)s style parameters
        params: Query parameters as dict
        columns: Column metadata for response

    Returns:
        MultiRowResponse with columns and data list
    """
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(query, params or {})
        rows = await cur.fetchall()
        return MultiRowResponse(
            columns=columns or [],
            data=[dict(row) for row in rows],
        )


async def execute_returning(
    conn: psycopg.AsyncConnection,
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Execute a query with RETURNING and return the row as dict."""
    async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute(query, params)
        return await cur.fetchone()


async def execute(
    conn: psycopg.AsyncConnection,
    query: str,
    params: tuple[Any, ...] | dict[str, Any] | None = None,
) -> int:
    """Execute a query and return the row count."""
    async with conn.cursor() as cur:
        await cur.execute(query, params)
        return cur.rowcount
