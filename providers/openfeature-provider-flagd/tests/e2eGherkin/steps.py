import time
import typing

import pytest
from pytest_bdd import given, parsers, then, when
from tests.e2e.parsers import to_bool

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import EventDetails, ProviderEvent

JsonPrimitive = typing.Union[str, bool, float, int]


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@given("a flagd provider is set", target_fixture="client")
def setup_provider() -> OpenFeatureClient:
    return api.get_client()


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
    evaluation_result = client.get_integer_details(key, default, evaluation_context)
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


provider_ready_ran = False


@when(parsers.cfparse("a PROVIDER_READY handler is added"))
def provider_ready_add(client: OpenFeatureClient):
    client.add_handler(ProviderEvent.PROVIDER_READY, provider_ready_handler)


def provider_ready_handler(event_details: EventDetails):
    global provider_ready_ran
    provider_ready_ran = True


@then(parsers.cfparse("the PROVIDER_READY handler must run"))
def provider_ready_was_executed(client: OpenFeatureClient):
    assert provider_ready_ran


provider_changed_ran = False


@when(parsers.cfparse("a PROVIDER_CONFIGURATION_CHANGED handler is added"))
def provider_changed_add(client: OpenFeatureClient):
    client.add_handler(
        ProviderEvent.PROVIDER_CONFIGURATION_CHANGED, provider_changed_handler
    )


def provider_changed_handler(event_details: EventDetails):
    global provider_changed_ran
    provider_changed_ran = True


@pytest.fixture(scope="function")
def context():
    return {}


@when(parsers.cfparse('a flag with key "{flag_key}" is modified'))
def assert_reason2(
    client: OpenFeatureClient,
    context,
    flag_key: str,
):
    context["flag_key"] = flag_key


@then(parsers.cfparse("the PROVIDER_CONFIGURATION_CHANGED handler must run"))
def provider_changed_was_executed(client: OpenFeatureClient):
    wait_for(lambda: provider_changed_ran)
    assert provider_changed_ran


def wait_for(pred, poll_sec=2, timeout_sec=10):
    start = time.time()
    while not (ok := pred()) and (time.time() - start < timeout_sec):
        time.sleep(poll_sec)
    assert pred()
    return ok
