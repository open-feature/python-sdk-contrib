import logging
import time

import pytest
from asserts import assert_greater
from pytest_bdd import given, parsers, then, when

from openfeature.client import OpenFeatureClient
from openfeature.event import ProviderEvent

events = {
    "ready": ProviderEvent.PROVIDER_READY,
    "error": ProviderEvent.PROVIDER_ERROR,
    "stale": ProviderEvent.PROVIDER_STALE,
    "change": ProviderEvent.PROVIDER_CONFIGURATION_CHANGED,
}


@pytest.fixture()
def event_handles() -> list:
    return []


@given(
    parsers.cfparse(
        "a {event_type} event handler",
    ),
)
def add_event_handler(client: OpenFeatureClient, event_type: str, event_handles: list):
    def handler(event):
        logging.warning((event_type, event))
        event_handles.append(
            {
                "type": event_type,
                "event": event,
            }
        )

    client.add_handler(events[event_type], handler)

    logging.warning(("handler added", event_type))


def assert_handlers(handles, event_type: str, max_wait: int = 2):
    poll_interval = 1
    while max_wait > 0:
        found = any(h["type"] == event_type for h in handles)
        if not found:
            max_wait -= poll_interval
            time.sleep(poll_interval)
            continue
        break
    return handles


@when(
    parsers.cfparse(
        "a {event_type} event was fired",
    ),
    target_fixture="event_details",
)
def pass_for_event_fired(event_type: str, event_handles):
    events = assert_handlers(event_handles, event_type, 30000)
    events = [e for e in events if e["type"] == event_type]
    assert_greater(len(events), 0)
    for event in event_handles:
        event_handles.remove(event)
    return events[0]["event"]


@then(
    parsers.cfparse(
        "the {event_type} event handler should have been executed",
    )
)
def assert_handler_run(event_type, event_handles):
    assert_handler_run_within(event_type, event_handles, 30000)


@then(
    parsers.cfparse(
        "the {event_type} event handler should have been executed within {time:d}ms",
    )
)
def assert_handler_run_within(event_type, event_handles, time: int):
    events = assert_handlers(event_handles, event_type, max_wait=int(time / 1000))
    assert_greater(len(events), 0)

    for event in event_handles:
        event_handles.remove(event)
