from e2e.conftest import SPEC_PATH
from pytest_bdd import scenarios
from tests.e2e.conftest import TEST_HARNESS_PATH

scenarios(f"{TEST_HARNESS_PATH}/gherkin", f"{SPEC_PATH}/specification/assets/gherkin")
