from dataclasses import dataclass

import psycopg
from litestar import Controller, get, post
from litestar.exceptions import HTTPException

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse


EVENTLOG_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="number"),
    ColumnMeta(key="logtype", label="Type", type="string"),
    ColumnMeta(key="logtime", label="Time", type="datetime"),
    ColumnMeta(key="descr", label="Description", type="string"),
]


@dataclass
class EventLogCreate:
    logtype: str
    descr: str | None = None


class EventLogController(Controller):
    path = "/api/eventlog"
    tags = ["eventlog"]

    @get()
    async def list_eventlog(
        self,
        conn: psycopg.AsyncConnection,
    ) -> MultiRowResponse:
        """List recent event log entries."""
        return await db.select_many(
            conn,
            """
            SELECT id, logtype, logtime, descr
            FROM yenotsys.eventlog
            ORDER BY logtime DESC
            LIMIT 50
            """,
            columns=EVENTLOG_COLUMNS,
        )

    @post(status_code=201)
    async def create_eventlog(
        self,
        conn: psycopg.AsyncConnection,
        data: EventLogCreate,
    ) -> SingleRowResponse:
        """Create a new event log entry."""
        row = await db.execute_returning(
            conn,
            """
            INSERT INTO yenotsys.eventlog (logtype, descr)
            VALUES (%(logtype)s, %(descr)s)
            RETURNING id, logtype, logtime, descr
            """,
            {"logtype": data.logtype, "descr": data.descr},
        )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create entry")
        return SingleRowResponse(columns=EVENTLOG_COLUMNS, data=row)
