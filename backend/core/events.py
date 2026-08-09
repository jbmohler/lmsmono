"""Change notifications carried over Postgres LISTEN/NOTIFY.

Write endpoints call `publish()` with their request connection, which issues a
`pg_notify` that Postgres delivers when the surrounding transaction commits - a
rolled-back write notifies nobody. One dedicated connection per backend process
LISTENs on the channel and fans each notification out to every subscribed SSE
stream.

Postgres is the fan-out point rather than an in-process pubsub so notifications
still reach every client when uvicorn runs more than one worker, or when the
backend scales past a single container.

Payloads are invalidation hints, not data: clients refetch through the normal
API, so authorization stays in one place and nothing crosses the channel that a
client could not already read.
"""

import asyncio
import contextlib
import dataclasses
import json
import traceback
from collections.abc import Iterator

import psycopg
import psycopg.sql


CHANNEL = "lms_changes"

# Bounded so one stalled reader cannot grow without limit. Events are hints, so
# dropping the oldest is safe - a client that misses one still refetches on the
# next event it does see.
QUEUE_SIZE = 64

RECONNECT_DELAY_SECONDS = 2.0


@dataclasses.dataclass
class ChangeEvent:
    """A committed change to a server-side resource.

    `entity` is the capability namespace of the resource ("transactions", not
    "transaction") so subscribers can be filtered with a plain f-string against
    the reader's capabilities.
    """

    entity: str
    action: str
    id: str | None = None
    actor: str | None = None

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self))


async def publish(
    conn: psycopg.AsyncConnection,
    entity: str,
    action: str,
    id: object | None = None,
    actor: str | None = None,
) -> None:
    """Queue a change notification on `conn`'s current transaction.

    Must be called with the request connection, not a fresh one, so delivery is
    tied to the same COMMIT as the write it describes.
    """
    event = ChangeEvent(
        entity=entity,
        action=action,
        id=str(id) if id is not None else None,
        actor=actor,
    )
    await conn.execute(
        "SELECT pg_notify(%(channel)s, %(payload)s)",
        {"channel": CHANNEL, "payload": event.to_json()},
    )


class Broker:
    """Owns the LISTEN connection and fans notifications out to subscribers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[ChangeEvent]] = set()
        self._task: asyncio.Task[None] | None = None
        self._conninfo = ""

    def start(self, conninfo: str) -> None:
        if self._task:
            return
        self._conninfo = conninfo
        self._task = asyncio.create_task(self._listen_forever())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    @contextlib.contextmanager
    def subscribe(self) -> Iterator[asyncio.Queue[ChangeEvent]]:
        """Yield a queue receiving every event published while it is open."""
        queue: asyncio.Queue[ChangeEvent] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    def dispatch(self, payload: str) -> None:
        """Hand one raw notification payload to every subscriber."""
        try:
            event = ChangeEvent(**json.loads(payload))
        except (TypeError, ValueError):
            print(f"Ignoring malformed change notification: {payload!r}")
            return

        for queue in self._subscribers:
            if queue.full():
                # Drop the oldest rather than block the listener on one slow
                # reader; see QUEUE_SIZE.
                queue.get_nowait()
            queue.put_nowait(event)

    async def _listen_forever(self) -> None:
        """Hold a LISTEN connection, reconnecting for as long as we run.

        This connection is deliberately outside the pool: it is held for the
        process lifetime, so borrowing from a pool of ten would permanently
        spend one of them.
        """
        listen = psycopg.sql.SQL("LISTEN {}").format(psycopg.sql.Identifier(CHANNEL))

        while True:
            try:
                # autocommit: LISTEN inside a transaction only takes effect at
                # commit, which would never arrive on an idle connection.
                async with await psycopg.AsyncConnection.connect(
                    self._conninfo, autocommit=True
                ) as conn:
                    await conn.execute(listen)
                    print(f"Listening for change notifications on {CHANNEL}")
                    async for notify in conn.notifies():
                        self.dispatch(notify.payload)
            except asyncio.CancelledError:
                raise
            except Exception:
                print(f"LISTEN connection lost, retrying in {RECONNECT_DELAY_SECONDS}s")
                print(traceback.format_exc())
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)


broker = Broker()
