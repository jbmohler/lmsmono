from dataclasses import dataclass

from litestar import Controller, get

import core.db as db


@dataclass
class HealthResponse:
    status: str
    config_loaded: bool
    database_host: str | None = None
    database_connected: bool = False
    database_version: str | None = None


class HealthController(Controller):
    path = "/api/health"
    tags = ["health"]

    @get()
    async def health_check(self) -> HealthResponse:
        from app import config

        db_connected = False
        db_version = None
        if db.pool:
            try:
                async with db.pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT version()")
                        row = await cur.fetchone()
                        if row:
                            db_connected = True
                            db_version = row[0]
            except Exception:
                pass

        return HealthResponse(
            status="ok",
            config_loaded=config is not None,
            database_host=config.database.host if config else None,
            database_connected=db_connected,
            database_version=db_version,
        )


class PingController(Controller):
    path = "/api/ping"
    tags = ["health"]

    @get()
    async def ping(self) -> dict:
        return {"message": "pong"}
