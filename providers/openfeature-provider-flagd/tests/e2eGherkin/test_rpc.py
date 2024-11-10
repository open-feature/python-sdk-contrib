import pytest
from pytest_bdd import scenarios
from testcontainers.core.container import DockerContainer
from tests.e2eGherkin.flagd_container import FlagDContainer
from tests.e2eGherkin.steps import wait_for

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus

container: DockerContainer = FlagDContainer()


@pytest.fixture(autouse=True, scope="package")
def setup(request):
    # Setup code
    c = container.start()
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.GRPC,
            port=int(container.get_exposed_port(8013)),
        )
    )
    client = api.get_client()
    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)

    def fin():
        c.stop()

    # Teardown code
    request.addfinalizer(fin)


scenarios(
    "../../test-harness/gherkin/flagd.feature",
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "../../spec/specification/assets/gherkin/evaluation.feature",
)
