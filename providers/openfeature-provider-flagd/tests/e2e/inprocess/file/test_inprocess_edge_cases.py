import pytest
from pytest_bdd import scenario
from tests.conftest import setup_flag_file

GHERKIN_FOLDER = "../../../../test-harness/gherkin/"


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "edge-case-flags.json")


@scenario(f"{GHERKIN_FOLDER}flagd-json-evaluator.feature", "Errors and edge cases")
def test_errors_and_edge_cases():
    """Errors and edge cases."""
