# as soon as we support all the features, we can actually remove this limitation to not run on Python 3.8
# Python 3.8 does not fully support tagging, hence that it will run all cases
import sys

from e2e.paths import TEST_HARNESS_PATH
from pytest_bdd import scenarios

if sys.version_info >= (3, 9):
    scenarios(f"{TEST_HARNESS_PATH}/gherkin")
