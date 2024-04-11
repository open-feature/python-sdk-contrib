import logging
import time

import pytest
from pytest_bdd import parsers, scenario, then, when
from tests.conftest import setup_flag_file

from openfeature.client import OpenFeatureClient, ProviderEvent


@scenario("../../test-harness/gherkin/flagd.feature", "Provider ready event")
def test_ready_event(caplog):
    """Provider ready event"""
    caplog.set_level(logging.DEBUG)


@scenario("../../test-harness/gherkin/flagd.feature", "Flag change event")
def test_change_event():
    """Flag change event"""


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "changing-flag-bar.json")


@pytest.fixture
def handles() -> list:
    return []


@when(
    parsers.cfparse(
        "a {event_type:ProviderEvent} handler is added",
        extra_types={"ProviderEvent": ProviderEvent},
    ),
    target_fixture="handles",
)
def add_event_handler(
    client: OpenFeatureClient, event_type: ProviderEvent, handles: list
):
    def handler(event):
        handles.append(
            {
                "type": event_type,
                "event": event,
            }
        )

    client.add_handler(event_type, handler)
    return handles


@then(
    parsers.cfparse(
        "the {event_type:ProviderEvent} handler must run",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_handler_run(handles, event_type: ProviderEvent):
    max_wait = 2
    poll_interval = 0.1
    while max_wait > 0:
        if all(h["type"] != event_type for h in handles):
            max_wait -= poll_interval
            time.sleep(poll_interval)
            continue
        break

    assert any(h["type"] == event_type for h in handles)


@when(parsers.cfparse('a flag with key "{key}" is modified'))
def modify_flag(flag_file, key):
    time.sleep(0.1)  # guard against race condition
    with open("test-harness/flags/changing-flag-foo.json") as src_file:
        contents = src_file.read()
    with open(flag_file, "w") as f:
        f.write(contents)


@then(parsers.cfparse('the event details must indicate "{key}" was altered'))
def assert_flag_changed(handles, key):
    handle = None
    for h in handles:
        if h["type"] == ProviderEvent.PROVIDER_CONFIGURATION_CHANGED:
            handle = h
            break

    assert handle is not None
    assert key in handle["event"].flags_changed
