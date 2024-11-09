import pytest
from pytest_bdd import scenarios
from testcontainers.core.container import DockerContainer
from tests.e2eGherkin.steps import wait_for

from openfeature import api
from openfeature.client import ProviderStatus
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType


@pytest.fixture(autouse=True, scope="module")
def setup(request):
    # Setup code
    with DockerContainer("ghcr.io/open-feature/flagd-testbed:v0.5.6").with_bind_ports(
        8013
    ) as container:
        container.start()
        api.set_provider(
            FlagdProvider(
                resolver_type=ResolverType.GRPC,
                port=int(container.get_exposed_port(8013)),
            )
        )
        client = api.get_client()
        wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
        assert client.get_provider_status() == ProviderStatus.READY

    def fin():
        container.stop()

    # Teardown code

    request.addfinalizer(fin)


scenarios(
    "../../test-harness/gherkin/flagd.feature",
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
)
