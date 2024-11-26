import pytest
from pytest_bdd import scenarios
from tests.e2e.conftest import TEST_HARNESS_PATH

from openfeature.contrib.provider.flagd.config import ResolverType


@pytest.fixture(autouse=True, scope="module")
def client_name() -> str:
    return "rpc-reconnect"


@pytest.fixture(autouse=True, scope="module")
def resolver_type() -> ResolverType:
    return ResolverType.RPC


@pytest.fixture(autouse=True, scope="module")
def port():
    return 8013


@pytest.fixture(autouse=True, scope="module")
def image():
    return "ghcr.io/open-feature/flagd-testbed-unstable:v0.5.13"


scenarios(
    f"{TEST_HARNESS_PATH}/gherkin/flagd-reconnect.feature",
)
