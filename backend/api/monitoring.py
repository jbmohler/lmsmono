from dataclasses import dataclass

import httpx
from litestar import Controller, get
from litestar.exceptions import HTTPException

import core.db as db


@dataclass
class DbPingResponse:
    status: str
    database_connected: bool
    pinged: bool


class MonitoringController(Controller):
    path = "/api/monitoring"
    tags = ["monitoring"]

    @get("/db")
    async def db_ping(self) -> DbPingResponse:
        """Cheap DB connectivity check for external uptime monitoring.

        Runs a trivial SELECT against the pool and, if it succeeds, pings
        the configured healthchecks.io check URL so a missed run alerts.
        Unauthenticated, matching /api/health and /api/ping, since this is
        meant to be hit by an external cron/monitor rather than a user.
        """
        from app import config

        if not db.pool:
            raise HTTPException(status_code=503, detail="Database pool not initialized")

        try:
            async with db.pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1")
                    await cur.fetchone()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Database check failed: {exc}") from exc

        ping_url = config.healthchecks.db_ping_url if config else ""
        pinged = False
        if ping_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(ping_url)
                    response.raise_for_status()
                pinged = True
            except httpx.HTTPError:
                # The DB check itself succeeded; a flaky ping just means
                # healthchecks.io will flag the missed check-in on its own.
                pass

        return DbPingResponse(status="ok", database_connected=True, pinged=pinged)
