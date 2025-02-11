from pytest_bdd import scenarios

from tests.e2e.paths import TEST_HARNESS_PATH

scenarios(f"{TEST_HARNESS_PATH}/gherkin")
