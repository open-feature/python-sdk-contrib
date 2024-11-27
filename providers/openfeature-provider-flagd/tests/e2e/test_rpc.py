import pytest
from pytest_bdd import scenario, scenarios
from tests.e2e.conftest import SPEC_PATH, TEST_HARNESS_PATH

from openfeature.contrib.provider.flagd.config import ResolverType


@pytest.fixture(autouse=True, scope="package")
def resolver_type() -> ResolverType:
    return ResolverType.GRPC


@pytest.fixture(autouse=True, scope="package")
def port():
    return 8013


@pytest.fixture(autouse=True, scope="package")
def image():
    return "ghcr.io/open-feature/flagd-testbed:v0.5.13"


@pytest.mark.skip(reason="Eventing not implemented")
@scenario(f"{TEST_HARNESS_PATH}/gherkin/flagd.feature", "Flag change event")
def test_flag_change_event():
    """not implemented"""


scenarios(
    f"{TEST_HARNESS_PATH}/gherkin/flagd.feature",
    f"{TEST_HARNESS_PATH}/gherkin/flagd-json-evaluator.feature",
    f"{SPEC_PATH}/specification/assets/gherkin/evaluation.feature",
)
