import pytest
from pytest_bdd import scenario, scenarios

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
@scenario("../../test-harness/gherkin/flagd.feature", "Flag change event")
def test_flag_change_event():
    """not implemented"""


scenarios(
    "../../test-harness/gherkin/flagd.feature",
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "../../spec/specification/assets/gherkin/evaluation.feature",
)
