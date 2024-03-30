import pytest
from pytest_bdd import scenario
from tests.conftest import setup_flag_file


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "evaluator-refs.json")


@scenario("../../test-harness/gherkin/flagd-json-evaluator.feature", "Evaluator reuse")
def test_evaluator_reuse():
    """Evaluator reuse."""
