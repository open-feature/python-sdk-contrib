import logging
import os
import time

import pytest
from pytest_bdd import given, parsers, scenario, then, when

from openfeature import api
from openfeature.client import OpenFeatureClient, ProviderEvent
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType


@scenario("../../test-harness/gherkin/flagd.feature", "Provider ready event")
@scenario("../../test-harness/gherkin/flagd.feature", "Flag change event")
def test_event_scenarios(caplog):
    caplog.set_level(logging.DEBUG)


@pytest.fixture
def flag_file(tmp_path):
    with open("test-harness/flags/changing-flag-bar.json") as src_file:
        contents = src_file.read()
    dst_path = os.path.join(tmp_path, "changing-flag-bar.json")
    with open(dst_path, "w") as dst_file:
        dst_file.write(contents)
    return dst_path


@pytest.fixture
def handles() -> list:
    return []


@given("a flagd provider is set", target_fixture="client")
def setup_provider(flag_file) -> OpenFeatureClient:
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=flag_file,
        )
    )
    return api.get_client()


# events
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
    if all(h["type"] != event_type for h in handles):
        time.sleep(2)

    assert any(h["type"] == event_type for h in handles)


@when(parsers.cfparse('a flag with key "{key}" is modified'))
def modify_flag(flag_file, key):
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
