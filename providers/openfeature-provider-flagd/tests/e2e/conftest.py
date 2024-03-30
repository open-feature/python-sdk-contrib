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
) -> tuple[str, JsonPrimitive]:
    return (key, default)


@when(
    parsers.cfparse('a context containing a key "{key}", with value "{value}"'),
    target_fixture="evaluation_context",
)
@when(
    parsers.cfparse('a context containing a key "{key}", with value {value:d}'),
    target_fixture="evaluation_context",
)
def update_context(
    evaluation_context: EvaluationContext, key: str, value: JsonPrimitive
) -> EvaluationContext:
    """a context containing a key and value."""
    evaluation_context.attributes[key] = value


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
