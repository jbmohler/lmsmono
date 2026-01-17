import contextlib
from typing import Any

import psycopg
import psycopg_pool


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


@contextlib.asynccontextmanager
async def get_connection():
    """Get a connection from the pool."""
    if not pool:
        raise RuntimeError("Database pool not initialized")
    async with pool.connection() as conn:
        yield conn


async def fetch_all(
    query: str, params: tuple[Any, ...] | None = None
) -> list[dict[str, Any]]:
    """Execute a query and return all rows as dicts."""
    async with get_connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(query, params)
            return await cur.fetchall()


async def fetch_one(
    query: str, params: tuple[Any, ...] | None = None
) -> dict[str, Any] | None:
    """Execute a query and return one row as dict."""
    async with get_connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()


async def execute(
    query: str, params: tuple[Any, ...] | None = None
) -> int:
    """Execute a query and return the row count."""
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            return cur.rowcount


async def execute_returning(
    query: str, params: tuple[Any, ...] | None = None
) -> dict[str, Any] | None:
    """Execute a query with RETURNING and return the row as dict."""
    async with get_connection() as conn:
        async with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(query, params)
            return await cur.fetchone()
