import typing

import pytest
from pytest_bdd import given, parsers, then, when
from tests.e2e.parsers import to_bool

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.evaluation_context import EvaluationContext

JsonPrimitive = typing.Union[str, bool, float, int]


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@given("a flagd provider is set", target_fixture="client")
def setup_provider(flag_file) -> OpenFeatureClient:
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=flag_file,
            offline_poll_interval_seconds=0.1,
        )
    )
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
