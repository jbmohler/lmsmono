"""Server-sent event stream carrying change notifications to the browser.

SSE rather than a websocket: traffic is server-to-client only, it rides the
existing session cookie with no second auth path, and the browser reconnects on
its own. See `core/events.py` for how notifications reach this process.
"""

import asyncio
from collections.abc import AsyncGenerator

from litestar import Controller, get
from litestar.response import ServerSentEvent, ServerSentEventMessage

import core.events as events
from core.auth import AuthenticatedUser


# Long enough to stay quiet, short enough to beat the 60s idle timeout that
# proxies between the browser and uvicorn commonly apply.
HEARTBEAT_SECONDS = 25.0


def may_read(user: AuthenticatedUser, entity: str) -> bool:
    """Whether `user` may know that `entity` changed.

    Capabilities are the snapshot taken when the stream opened. That is fine
    for hints - a client acts on one by refetching, and that request is
    authorized fresh - but it means a capability revoked mid-stream still leaks
    the fact that something changed until the client reconnects.
    """
    return f"{entity}:read" in user.capabilities


async def change_stream(
    user: AuthenticatedUser,
) -> AsyncGenerator[ServerSentEventMessage, None]:
    with events.broker.subscribe() as queue:
        # Push a first chunk immediately rather than leaving the stream silent
        # until something changes: it settles the response through every proxy
        # in the chain right away, so a buffering misconfiguration shows up at
        # connect time instead of the first time a user saves something.
        yield ServerSentEventMessage(event="ready", data="")

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield ServerSentEventMessage(comment="ping")
                continue

            if may_read(user, event.entity):
                yield ServerSentEventMessage(data=event.to_json())


class EventsController(Controller):
    path = "/api/events"
    tags = ["events"]

    # No `conn` dependency anywhere in this controller: the stream is held for
    # hours, and taking a pooled connection would spend one of ten per tab.
    @get()
    async def stream(self, current_user: AuthenticatedUser) -> ServerSentEvent:
        """Stream change notifications for as long as the client stays."""
        return ServerSentEvent(
            change_stream(current_user),
            # Defeats nginx response buffering even where the proxy config has
            # not been updated; without it events arrive in clumps.
            headers={"X-Accel-Buffering": "no"},
        )
