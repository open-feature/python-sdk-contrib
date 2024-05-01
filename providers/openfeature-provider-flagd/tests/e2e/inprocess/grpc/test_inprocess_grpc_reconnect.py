import pytest
from pytest_bdd import scenarios

GHERKIN_FOLDER = "../../../../test-harness/gherkin/"

scenarios(f"{GHERKIN_FOLDER}flagd-reconnect.feature")


@pytest.fixture
def port():
    # Port for flagd-sync-unstable, overrides main conftest port
    return 9091
