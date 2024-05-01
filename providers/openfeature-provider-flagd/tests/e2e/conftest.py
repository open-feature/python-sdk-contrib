import logging
import time
import typing

import pytest
from pytest_bdd import parsers, then, when

from openfeature.client import OpenFeatureClient, ProviderEvent
from openfeature.evaluation_context import EvaluationContext

JsonPrimitive = typing.Union[str, bool, float, int]


def to_bool(s: str) -> bool:
    return s.lower() == "true"


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@when(
    parsers.cfparse(
        'a zero-value boolean flag with key "{key}" is evaluated with default value "{default:bool}"',
        extra_types={"bool": to_bool},
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a zero-value string flag with key "{key}" is evaluated with default value "{default}"',
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a string flag with key "{key}" is evaluated with default value "{default}"'
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a zero-value integer flag with key "{key}" is evaluated with default value {default:d}',
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'an integer flag with key "{key}" is evaluated with default value {default:d}',
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a zero-value float flag with key "{key}" is evaluated with default value {default:f}',
    ),
    target_fixture="key_and_default",
)
def setup_key_and_default(
    key: str, default: JsonPrimitive
) -> typing.Tuple[str, JsonPrimitive]:
    return (key, default)


@when(
    parsers.cfparse(
        'a context containing a targeting key with value "{targeting_key}"'
    ),
)
def assign_targeting_context(evaluation_context: EvaluationContext, targeting_key: str):
    """a context containing a targeting key with value <targeting key>."""
    evaluation_context.targeting_key = targeting_key


@when(
    parsers.cfparse('a context containing a key "{key}", with value "{value}"'),
)
@when(
    parsers.cfparse('a context containing a key "{key}", with value {value:d}'),
)
def update_context(
    evaluation_context: EvaluationContext, key: str, value: JsonPrimitive
):
    """a context containing a key and value."""
    evaluation_context.attributes[key] = value


@when(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value "{value}"'
    ),
)
@when(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value {value:d}'
    ),
)
def update_context_nested(
    evaluation_context: EvaluationContext,
    outer: str,
    inner: str,
    value: typing.Union[str, int],
):
    """a context containing a nested property with outer key, and inner key, and value."""
    if outer not in evaluation_context.attributes:
        evaluation_context.attributes[outer] = {}
    evaluation_context.attributes[outer][inner] = value


@then(
    parsers.cfparse(
        'the resolved boolean zero-value should be "{expected_value:bool}"',
        extra_types={"bool": to_bool},
    )
)
def assert_boolean_value(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_boolean_value(key, default, evaluation_context)
    assert evaluation_result == expected_value


@then(
    parsers.cfparse(
        "the resolved integer zero-value should be {expected_value:d}",
    )
)
@then(parsers.cfparse("the returned value should be {expected_value:d}"))
def assert_integer_value(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_integer_value(key, default, evaluation_context)
    assert evaluation_result == expected_value


@then(
    parsers.cfparse(
        "the resolved float zero-value should be {expected_value:f}",
    )
)
def assert_float_value(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_float_value(key, default, evaluation_context)
    assert evaluation_result == expected_value


@then(parsers.cfparse('the returned value should be "{expected_value}"'))
def assert_string_value(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_string_value(key, default, evaluation_context)
    assert evaluation_result == expected_value


@then(
    parsers.cfparse(
        'the resolved string zero-value should be ""',
    )
)
def assert_empty_string(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_string_value(key, default, evaluation_context)
    assert evaluation_result == ""


@then(parsers.cfparse('the returned reason should be "{reason}"'))
def assert_reason(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
    reason: str,
):
    """the returned reason should be <reason>."""
    key, default = key_and_default
    evaluation_result = client.get_string_details(key, default, evaluation_context)
    assert evaluation_result.reason.value == reason


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
        logging.info((event_type, event))
        handles.append(
            {
                "type": event_type,
                "event": event,
            }
        )

    client.add_handler(event_type, handler)
    return handles


@when(
    parsers.cfparse(
        "a {event_type:ProviderEvent} handler and a {event_type2:ProviderEvent} handler are added",
        extra_types={"ProviderEvent": ProviderEvent},
    ),
    target_fixture="handles",
)
def add_event_handlers(
    client: OpenFeatureClient,
    event_type: ProviderEvent,
    event_type2: ProviderEvent,
    handles: list,
):
    add_event_handler(client, event_type, handles)
    add_event_handler(client, event_type2, handles)


def assert_handlers(
    handles, event_type: ProviderEvent, max_wait: int = 2, num_events: int = 1
):
    poll_interval = 0.05
    while max_wait > 0:
        if sum([h["type"] == event_type for h in handles]) < num_events:
            max_wait -= poll_interval
            time.sleep(poll_interval)
            continue
        break

    logging.info(f"asserting num({event_type}) >= {num_events}: {handles}")
    actual_num_events = sum([h["type"] == event_type for h in handles])
    assert (
        num_events <= actual_num_events
    ), f"Expected {num_events} but got {actual_num_events}: {handles}"


@then(
    parsers.cfparse(
        "the {event_type:ProviderEvent} handler must run",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
@then(
    parsers.cfparse(
        "the {event_type:ProviderEvent} handler must run when the provider connects",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_handler_run(handles, event_type: ProviderEvent):
    assert_handlers(handles, event_type, max_wait=3)


@then(
    parsers.cfparse(
        "the {event_type:ProviderEvent} handler must run when the provider's connection is lost",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_disconnect_handler(handles, event_type: ProviderEvent):
    assert_handlers(handles, event_type, max_wait=6)


@then(
    parsers.cfparse(
        "when the connection is reestablished the {event_type:ProviderEvent} handler must run again",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_disconnect_error(client: OpenFeatureClient, event_type: ProviderEvent):
    reconnect_handles = []
    add_event_handler(client, event_type, reconnect_handles)
    assert_handlers(reconnect_handles, event_type, max_wait=6)


@then(parsers.cfparse('the event details must indicate "{key}" was altered'))
def assert_flag_changed(handles, key):
    handle = None
    for h in handles:
        if h["type"] == ProviderEvent.PROVIDER_CONFIGURATION_CHANGED:
            handle = h
            break

    assert handle is not None
    assert key in handle["event"].flags_changed
