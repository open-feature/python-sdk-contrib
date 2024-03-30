import os

import pytest
from pytest_bdd import given, parsers, scenario, then, when
from tests.e2e.parsers import to_bool

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

# scenario = partial(pytest_bdd.scenario, "../../test-harness/gherkin/flagd.feature")


@scenario("../../test-harness/gherkin/flagd.feature", "Resolves boolean zero value")
@scenario("../../test-harness/gherkin/flagd.feature", "Resolves string zero value")
@scenario("../../test-harness/gherkin/flagd.feature", "Resolves integer zero value")
@scenario("../../test-harness/gherkin/flagd.feature", "Resolves float zero value")
def test_event_scenarios():
    pass


@pytest.fixture
def flag_file(tmp_path):
    with open("test-harness/flags/zero-flags.json") as src_file:
        contents = src_file.read()
    dst_path = os.path.join(tmp_path, "zero-flags.json")
    with open(dst_path, "w") as dst_file:
        dst_file.write(contents)
    return dst_path


@given("a flagd provider is set", target_fixture="client")
def setup_provider(flag_file) -> OpenFeatureClient:
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=flag_file,
        )
    )
    return api.get_client()


# zero evaluation
@when(
    parsers.cfparse(
        'a zero-value boolean flag with key "{key}" is evaluated with default value "{default:bool}"',
        extra_types={"bool": to_bool},
    ),
    target_fixture="evaluation_result",
)
def evaluate_bool(client: OpenFeatureClient, key: str, default: bool) -> bool:
    return client.get_boolean_value(key, default)


@when(
    parsers.cfparse(
        'a zero-value string flag with key "{key}" is evaluated with default value "{default}"',
    ),
    target_fixture="evaluation_result_str",
)
def evaluate_string(client: OpenFeatureClient, key: str, default: str) -> str:
    return client.get_string_value(key, default)


@when(
    parsers.cfparse(
        'a zero-value integer flag with key "{key}" is evaluated with default value {default:d}',
    ),
    target_fixture="evaluation_result",
)
def evaluate_integer(client: OpenFeatureClient, key: str, default: int) -> int:
    return client.get_integer_value(key, default)


@when(
    parsers.cfparse(
        'a zero-value float flag with key "{key}" is evaluated with default value {default:f}',
    ),
    target_fixture="evaluation_result",
)
def evaluate_float(client: OpenFeatureClient, key: str, default: float) -> float:
    return client.get_float_value(key, default)


@then(
    parsers.cfparse(
        'the resolved boolean zero-value should be "{expected_value:bool}"',
        extra_types={"bool": to_bool},
    )
)
@then(
    parsers.cfparse(
        "the resolved integer zero-value should be {expected_value:d}",
    )
)
@then(
    parsers.cfparse(
        "the resolved float zero-value should be {expected_value:f}",
    )
)
def assert_value(evaluation_result, expected_value):
    assert evaluation_result == expected_value


@then(
    parsers.cfparse(
        'the resolved string zero-value should be ""',
    )
)
def assert_empty_string(evaluation_result_str):
    assert evaluation_result_str == ""
