import logging
import time
import typing

import pytest
from asserts import assert_equal, assert_in, assert_not_equal, assert_true
from pytest_bdd import given, parsers, then, when
from tests.e2e.parsers import to_bool, to_list

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEvent
from openfeature.flag_evaluation import ErrorCode, FlagEvaluationDetails, Reason
from openfeature.provider import ProviderStatus

JsonObject = typing.Union[dict, list]
JsonPrimitive = typing.Union[str, bool, float, int, JsonObject]


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@given("a flagd provider is set", target_fixture="client")
@given("a provider is registered", target_fixture="client")
def setup_provider(setup, resolver_type, client_name) -> OpenFeatureClient:
    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            port=setup,
        ),
        client_name,
    )
    client = api.get_client(client_name)
    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client


@when(
    parsers.cfparse(
        'a {ignored:s?}boolean flag with key "{key}" is evaluated with {details:s?}default value "{default:bool}"',
        extra_types={"bool": to_bool, "s": str},
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a {ignored:s?}string flag with key "{key}" is evaluated with {details:s?}default value "{default}"',
        extra_types={"s": str},
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a{ignored:s?} integer flag with key "{key}" is evaluated with {details:s?}default value {default:d}',
        extra_types={"s": str},
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a {ignored:s?}float flag with key "{key}" is evaluated with {details:s?}default value {default:f}',
        extra_types={"s": str},
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a string flag with key "{key}" is evaluated as an integer, with details and a default value {default:d}',
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'a flag with key "{key}" is evaluated with default value "{default}"',
    ),
    target_fixture="key_and_default",
)
def setup_key_and_default(
    key: str, default: JsonPrimitive
) -> typing.Tuple[str, JsonPrimitive]:
    return (key, default)


@when(
    parsers.cfparse(
        'an object flag with key "{key}" is evaluated with a null default value',
    ),
    target_fixture="key_and_default",
)
@when(
    parsers.cfparse(
        'an object flag with key "{key}" is evaluated with details and a null default value',
    ),
    target_fixture="key_and_default",
)
def setup_key_and_default_for_object(key: str) -> typing.Tuple[str, JsonObject]:
    return (key, {})


@when(
    parsers.cfparse(
        'a context containing a targeting key with value "{targeting_key}"'
    ),
)
def assign_targeting_context(evaluation_context: EvaluationContext, targeting_key: str):
    """a context containing a targeting key with value <targeting key>."""
    evaluation_context.targeting_key = targeting_key


@when(
    parsers.cfparse(
        'context contains keys {fields:s} with values "{svalue}", "{svalue2}", {ivalue:d}, "{bvalue:bool}"',
        extra_types={"bool": to_bool, "s": to_list},
    ),
)
def assign_targeting_context_2(
    evaluation_context: EvaluationContext,
    fields: list,
    svalue: str,
    svalue2: str,
    ivalue: int,
    bvalue: bool,
):
    evaluation_context.attributes[fields[0]] = svalue
    evaluation_context.attributes[fields[1]] = svalue2
    evaluation_context.attributes[fields[2]] = ivalue
    evaluation_context.attributes[fields[3]] = bvalue


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
        'the resolved boolean value should be "{expected_value:bool}"',
        extra_types={"bool": to_bool},
    )
)
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
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved boolean details value should be "{expected_value:bool}", the variant should be "{variant}", and the reason should be "{reason}"',
        extra_types={"bool": to_bool},
    )
)
def assert_boolean_value_with_details(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    variant: str,
    reason: str,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_boolean_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, expected_value)
    assert_equal(evaluation_result.reason, reason)
    assert_equal(evaluation_result.variant, variant)


@then(
    parsers.cfparse(
        "the resolved integer {ignored:s?}value should be {expected_value:d}",
        extra_types={"s": str},
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
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved integer details value should be {expected_value:d}, the variant should be "{variant}", and the reason should be "{reason}"',
    )
)
def assert_integer_value_with_details(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: int,
    variant: str,
    reason: str,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_integer_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, expected_value)
    assert_equal(evaluation_result.reason, reason)
    assert_equal(evaluation_result.variant, variant)


@then(
    parsers.cfparse(
        "the resolved float {ignored:s?}value should be {expected_value:f}",
        extra_types={"s": str},
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
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved float details value should be {expected_value:f}, the variant should be "{variant}", and the reason should be "{reason}"',
    )
)
def assert_float_value_with_details(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: float,
    variant: str,
    reason: str,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_float_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, expected_value)
    assert_equal(evaluation_result.reason, reason)
    assert_equal(evaluation_result.variant, variant)


@then(parsers.cfparse('the returned value should be "{expected_value}"'))
def assert_string_value(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: bool,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_details = client.get_string_details(key, default, evaluation_context)
    assert_equal(evaluation_details.value, expected_value)


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
    assert_string(client, key_and_default, evaluation_context, "")


@then(
    parsers.cfparse(
        'the resolved string value should be "{expected_value}"',
    )
)
def assert_string(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
    expected_value: str,
):
    key, default = key_and_default
    evaluation_result = client.get_string_value(key, default, evaluation_context)
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved string response should be "{expected_value}"',
    )
)
def assert_string_response(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
    expected_value: str,
):
    key, default = key_and_default
    evaluation_result = client.get_string_value(key, default, evaluation_context)
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved flag value is "{expected_value}" when the context is empty',
    )
)
def assert_string_without_context(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
    expected_value: str,
):
    key, default = key_and_default
    evaluation_result = client.get_string_value(key, default, None)
    assert_equal(evaluation_result, expected_value)


@then(
    parsers.cfparse(
        'the resolved object {details:s?}value should be contain fields "{bool_field}", "{string_field}", and "{int_field}", with values "{bvalue:bool}", "{svalue}" and {ivalue:d}, respectively',
        extra_types={"bool": to_bool, "s": str},
    ),
    target_fixture="evaluation_details",
)
def assert_object(  # noqa: PLR0913
    client: OpenFeatureClient,
    key_and_default: tuple,
    bool_field: str,
    string_field: str,
    int_field: str,
    bvalue: bool,
    svalue: str,
    ivalue: int,
    details: str,
) -> FlagEvaluationDetails:
    key, default = key_and_default
    if details:
        evaluation_result = client.get_object_details(key, default)
        value = evaluation_result.value
        assert_in(bool_field, value)
        assert_in(string_field, value)
        assert_in(string_field, value)
        assert_equal(value[bool_field], bvalue)
        assert_equal(value[string_field], svalue)
        assert_equal(value[int_field], ivalue)
        return evaluation_result
    else:
        evaluation_result = client.get_object_value(key, default)
        assert_in(bool_field, evaluation_result)
        assert_in(string_field, evaluation_result)
        assert_in(string_field, evaluation_result)
        assert_equal(evaluation_result[bool_field], bvalue)
        assert_equal(evaluation_result[string_field], svalue)
        assert_equal(evaluation_result[int_field], ivalue)
        assert_not_equal(evaluation_result, None)


@then(
    parsers.cfparse(
        'the variant should be "{variant}", and the reason should be "{reason}"',
    )
)
def assert_for_variant_and_reason(
    client: OpenFeatureClient,
    evaluation_details: FlagEvaluationDetails,
    variant: str,
    reason: str,
):
    assert_equal(evaluation_details.reason, Reason[reason])
    assert_equal(evaluation_details.variant, variant)


@then(
    parsers.cfparse(
        "the default string value should be returned",
    ),
    target_fixture="evaluation_details",
)
def assert_default_string(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
) -> FlagEvaluationDetails[str]:
    key, default = key_and_default
    evaluation_result = client.get_string_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, default)
    return evaluation_result


@then(
    parsers.cfparse(
        "the default integer value should be returned",
    ),
    target_fixture="evaluation_details",
)
def assert_default_integer(
    client: OpenFeatureClient,
    key_and_default: tuple,
    evaluation_context: EvaluationContext,
) -> FlagEvaluationDetails[int]:
    key, default = key_and_default
    evaluation_result = client.get_integer_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, default)
    return evaluation_result


@then(
    parsers.cfparse(
        'the reason should indicate an error and the error code should indicate a missing flag with "{error}"',
    )
)
@then(
    parsers.cfparse(
        'the reason should indicate an error and the error code should indicate a type mismatch with "{error}"',
    )
)
def assert_for_error(
    client: OpenFeatureClient,
    evaluation_details: FlagEvaluationDetails,
    error: str,
):
    assert_equal(evaluation_details.error_code, ErrorCode[error])
    assert_equal(evaluation_details.reason, Reason.ERROR)


@then(
    parsers.cfparse(
        'the resolved string details value should be "{expected_value}", the variant should be "{variant}", and the reason should be "{reason}"',
        extra_types={"bool": to_bool},
    )
)
def assert_string_value_with_details(
    client: OpenFeatureClient,
    key_and_default: tuple,
    expected_value: str,
    variant: str,
    reason: str,
    evaluation_context: EvaluationContext,
):
    key, default = key_and_default
    evaluation_result = client.get_string_details(key, default, evaluation_context)
    assert_equal(evaluation_result.value, expected_value)
    assert_equal(evaluation_result.reason, reason)
    assert_equal(evaluation_result.variant, variant)


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
    assert_equal(evaluation_result.reason, reason)


@pytest.fixture()
def event_handles() -> list:
    return []


@pytest.fixture()
def error_handles() -> list:
    return []


@when(
    parsers.cfparse(
        "a {event_type:ProviderEvent} handler is added",
        extra_types={"ProviderEvent": ProviderEvent},
    ),
)
def add_event_handler(
    client: OpenFeatureClient, event_type: ProviderEvent, event_handles: list
):
    def handler(event):
        logging.debug((event_type, event))
        event_handles.append(
            {
                "type": event_type,
                "event": event,
            }
        )

    client.add_handler(event_type, handler)


@pytest.fixture(scope="function")
def context():
    return {}


@when(
    parsers.cfparse(
        "a {event_type:ProviderEvent} handler and a {event_type2:ProviderEvent} handler are added",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def add_event_handlers(
    client: OpenFeatureClient,
    event_type: ProviderEvent,
    event_type2: ProviderEvent,
    event_handles,
    error_handles,
):
    add_event_handler(client, event_type, event_handles)
    add_event_handler(client, event_type2, error_handles)


def assert_handlers(
    handles, event_type: ProviderEvent, max_wait: int = 2, num_events: int = 1
):
    poll_interval = 1
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
def assert_handler_run(event_type: ProviderEvent, event_handles):
    assert_handlers(event_handles, event_type, max_wait=6)


@then(
    parsers.cfparse(
        "the {event_type:ProviderEvent} handler must run when the provider's connection is lost",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_disconnect_handler(error_handles, event_type: ProviderEvent):
    # docker sync upstream restarts every 5s, waiting 2 cycles reduces test noise
    assert_handlers(error_handles, event_type, max_wait=30)


@when(
    parsers.cfparse('a flag with key "{flag_key}" is modified'),
    target_fixture="changed_flag",
)
def changed_flag(
    flag_key: str,
):
    return flag_key


@then(
    parsers.cfparse(
        "when the connection is reestablished the {event_type:ProviderEvent} handler must run again",
        extra_types={"ProviderEvent": ProviderEvent},
    )
)
def assert_disconnect_error(
    client: OpenFeatureClient, event_type: ProviderEvent, event_handles: list
):
    assert_handlers(event_handles, event_type, max_wait=30, num_events=2)


@then(parsers.cfparse('the event details must indicate "{key}" was altered'))
def assert_flag_changed(event_handles, key):
    handle = None
    for h in event_handles:
        if h["type"] == ProviderEvent.PROVIDER_CONFIGURATION_CHANGED:
            handle = h
            break

    assert handle is not None
    assert key in handle["event"].flags_changed


def wait_for(pred, poll_sec=2, timeout_sec=10):
    start = time.time()
    while not (ok := pred()) and (time.time() - start < timeout_sec):
        time.sleep(poll_sec)
    assert_true(pred())
    return ok


@given("flagd is unavailable", target_fixture="client")
def flagd_unavailable(resolver_type):
    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            port=99999,
        ),
        "unavailable",
    )
    return api.get_client("unavailable")


@when("a flagd provider is set and initialization is awaited")
def flagd_init(client: OpenFeatureClient, event_handles, error_handles):
    add_event_handler(client, ProviderEvent.PROVIDER_ERROR, error_handles)
    add_event_handler(client, ProviderEvent.PROVIDER_READY, event_handles)


@then("an error should be indicated within the configured deadline")
def flagd_error(error_handles):
    assert_handlers(error_handles, ProviderEvent.PROVIDER_ERROR)
