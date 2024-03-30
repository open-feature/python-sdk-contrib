import pytest
from pytest_bdd import scenario
from tests.conftest import setup_flag_file


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "custom-ops.json")


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
