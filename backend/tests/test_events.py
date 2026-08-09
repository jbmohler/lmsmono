"""Unit tests for change-notification fan-out and stream authorization."""

import json

import api.events as events_api
import core.events as events
from core.auth import AuthenticatedUser


def make_payload(entity: str = "transactions", action: str = "created") -> str:
    return events.ChangeEvent(
        entity=entity, action=action, id="abc", actor="u1"
    ).to_json()


def test_dispatch_reaches_every_subscriber():
    broker = events.Broker()

    with broker.subscribe() as first, broker.subscribe() as second:
        broker.dispatch(make_payload())

        for queue in (first, second):
            event = queue.get_nowait()
            assert event.entity == "transactions"
            assert event.action == "created"
            assert event.id == "abc"
            assert event.actor == "u1"


def test_unsubscribed_queue_stops_receiving():
    broker = events.Broker()

    with broker.subscribe() as queue:
        pass

    broker.dispatch(make_payload())
    assert queue.empty()


def test_malformed_payload_is_ignored():
    broker = events.Broker()

    with broker.subscribe() as queue:
        broker.dispatch("not json")
        broker.dispatch(json.dumps({"unexpected": "shape"}))

        assert queue.empty()

        # The listener survives to deliver the next good event.
        broker.dispatch(make_payload())
        assert queue.get_nowait().entity == "transactions"


def test_full_queue_drops_oldest():
    broker = events.Broker()

    with broker.subscribe() as queue:
        for i in range(events.QUEUE_SIZE + 1):
            broker.dispatch(make_payload(action=str(i)))

        assert queue.qsize() == events.QUEUE_SIZE
        # The first event was evicted, the most recent survived.
        assert queue.get_nowait().action == "1"


def test_publish_payload_fits_the_notify_limit():
    payload = events.ChangeEvent(
        entity="transactions",
        action="updated",
        id="0" * 36,
        actor="0" * 36,
    ).to_json()

    # NOTIFY payloads are capped at 8000 bytes by Postgres.
    assert len(payload.encode()) < 8000


def test_stream_filters_by_read_capability():
    reader = AuthenticatedUser(
        id="u1",
        username="reader",
        full_name=None,
        capabilities={"transactions:read"},
    )

    assert events_api.may_read(reader, "transactions")
    assert not events_api.may_read(reader, "contacts")
    # Write access alone does not imply the right to see change hints.
    assert not events_api.may_read(
        AuthenticatedUser(
            id="u2", username="writer", full_name=None, capabilities={"contacts:write"}
        ),
        "contacts",
    )
