import typing

import pytest
from pytest_bdd import parsers, scenario, then, when
from tests.conftest import setup_flag_file

from openfeature.evaluation_context import EvaluationContext


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "custom-ops.json")


# @scenario( "../../test-harness/gherkin/flagd-json-evaluator.feature", "Errors and edge cases")
# def test_errors_and_edge_cases():
#     """Errors and edge cases."""


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature", "Fractional operator"
)
def test_fractional_operator():
    """Fractional operator."""


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "Semantic version operator numeric comparison",
)
def test_semantic_version_operator_numeric_comparison():
    """Semantic version operator numeric comparison."""


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "Semantic version operator semantic comparison",
)
def test_semantic_version_operator_semantic_comparison():
    """Semantic version operator semantic comparison."""


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature", "Substring operators"
)
def test_substring_operators():
    """Substring operators."""


# @scenario( "../../test-harness/gherkin/flagd-json-evaluator.feature", "Targeting by targeting key")
# def test_targeting_by_targeting_key():
#     """Targeting by targeting key."""


@when('a context containing a key "id", with value <id>')
def _():
    """a context containing a key "id", with value <id>."""
    raise NotImplementedError


@when('a context containing a key "time", with value <time>')
def _():
    """a context containing a key "time", with value <time>."""
    raise NotImplementedError


@when('a context containing a key "version", with value <version>')
def _():
    """a context containing a key "version", with value <version>."""
    raise NotImplementedError


@when(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value "{value}"'
    ),
    target_fixture="evaluation_context",
)
@when(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value {value:d}'
    ),
    target_fixture="evaluation_context",
)
def nested_context(
    outer: str, inner: str, value: typing.Union[str, int]
) -> EvaluationContext:
    """a context containing a nested property with outer key, and inner key, and value."""
    return EvaluationContext(attributes={outer: {inner: value}})


@when("a context containing a targeting key with value <targeting key>")
def _():
    """a context containing a targeting key with value <targeting key>."""
    raise NotImplementedError


@then("the returned reason should be <reason>")
def _():
    """the returned reason should be <reason>."""
    raise NotImplementedError
