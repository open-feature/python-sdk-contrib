import pytest
from pytest_bdd import scenario
from tests.conftest import setup_flag_file

GHERKIN_FOLDER = "../../../../test-harness/gherkin/"


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Resolves boolean zero value")
def test_eval_boolean():
    """Resolve boolean zero value"""


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Resolves string zero value")
def test_eval_string():
    """Resolve string zero value"""


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Resolves integer zero value")
def test_eval_integer():
    """Resolve integer zero value"""


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Resolves float zero value")
def test_eval_float():
    """Resolve float zero value"""


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "zero-flags.json")