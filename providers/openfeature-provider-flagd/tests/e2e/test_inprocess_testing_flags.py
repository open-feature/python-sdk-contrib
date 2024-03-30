import pytest
from pytest_bdd import scenario
from tests.conftest import setup_flag_file


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "testing-flags.json")


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "Time-based operations",
)
def test_timebased_operations():
    """Time-based operations."""


@scenario(
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "Targeting by targeting key",
)
def test_targeting_by_targeting_key():
    """Targeting by targeting key."""
