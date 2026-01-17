import contextlib
import datetime
import json
import os
import pathlib

import fastapi
import pydantic

import db


class HealthResponse(pydantic.BaseModel):
    status: str
    config_loaded: bool
    database_host: str | None = None
    database_connected: bool = False


class EventLogEntry(pydantic.BaseModel):
    id: int
    logtype: str
    logtime: datetime.datetime
    descr: str | None = None


class EventLogCreate(pydantic.BaseModel):
    logtype: str
    descr: str | None = None


config: dict = {}


def build_conninfo() -> str:
    """Build psycopg connection string from config."""
    db_config = config.get("database", {})
    return (
        f"host={db_config.get('host', 'localhost')} "
        f"port={db_config.get('port', 5432)} "
        f"dbname={db_config.get('name', 'lms')} "
        f"user={db_config.get('user', 'lms')} "
        f"password={db_config.get('password', '')}"
    )


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    global config
    config_path = os.environ.get("CONFIG_FILE", "/run/secrets/config.json")

    if pathlib.Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
        print(f"Config loaded from {config_path}")
    else:
        print(f"Warning: Config file not found at {config_path}")

    # Initialize database pool
    if config.get("database"):
        conninfo = build_conninfo()
        await db.init_pool(conninfo)
        print("Database pool initialized")

    yield

    # Cleanup
    await db.close_pool()
    print("Database pool closed")


app = fastapi.FastAPI(title="LMS API", lifespan=lifespan)


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    db_connected = False
    if db.pool:
        try:
            result = await db.fetch_one("SELECT 1 as ok")
            db_connected = result is not None
        except Exception:
            db_connected = False

    return HealthResponse(
        status="ok",
        config_loaded=bool(config),
        database_host=config.get("database", {}).get("host"),
        database_connected=db_connected,
    )


@app.get("/api/ping")
async def ping() -> dict:
    return {"message": "pong"}


@app.get("/api/eventlog", response_model=list[EventLogEntry])
async def list_eventlog() -> list[EventLogEntry]:
    """List recent event log entries."""
    rows = await db.fetch_all(
        """
        SELECT id, logtype, logtime, descr
        FROM yenotsys.eventlog
        ORDER BY logtime DESC
        LIMIT 50
        """
    )
    return [EventLogEntry(**row) for row in rows]


@app.post("/api/eventlog", response_model=EventLogEntry, status_code=201)
async def create_eventlog(entry: EventLogCreate) -> EventLogEntry:
    """Create a new event log entry."""
    row = await db.execute_returning(
        """
        INSERT INTO yenotsys.eventlog (logtype, descr)
        VALUES (%s, %s)
        RETURNING id, logtype, logtime, descr
        """,
        (entry.logtype, entry.descr),
    )
    if not row:
        raise fastapi.HTTPException(status_code=500, detail="Failed to create entry")
    return EventLogEntry(**row)
