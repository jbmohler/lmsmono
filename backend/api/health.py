from dataclasses import dataclass

from litestar import Controller, get

import core.db as db


@dataclass
class HealthResponse:
    status: str
    config_loaded: bool
    database_host: str | None = None
    database_connected: bool = False


class HealthController(Controller):
    path = "/api/health"
    tags = ["health"]

    @get()
    async def health_check(self) -> HealthResponse:
        from app import config

        db_connected = False
        if db.pool:
            try:
                async with db.pool.connection() as conn:
                    async with conn.cursor() as cur:
                        await cur.execute("SELECT 1")
                        db_connected = True
            except Exception:
                pass

        return HealthResponse(
            status="ok",
            config_loaded=config is not None,
            database_host=config.database.host if config else None,
            database_connected=db_connected,
        )


class PingController(Controller):
    path = "/api/ping"
    tags = ["health"]

    @get()
    async def ping(self) -> dict:
        return {"message": "pong"}
