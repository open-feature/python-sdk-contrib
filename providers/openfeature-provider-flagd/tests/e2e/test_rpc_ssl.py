from pathlib import Path

import pytest
from pytest_bdd import given, scenarios
from tests.e2e.conftest import SPEC_PATH
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.steps import wait_for

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus


@pytest.fixture(autouse=True, scope="module")
def client_name() -> str:
    return "rpc"


@pytest.fixture(autouse=True, scope="module")
def resolver_type() -> ResolverType:
    return ResolverType.RPC


@pytest.fixture(autouse=True, scope="module")
def port():
    return 8013


@pytest.fixture(autouse=True, scope="module")
def image():
    return "ghcr.io/open-feature/flagd-testbed-ssl"


@given("a flagd provider is set", target_fixture="client")
@given("a provider is registered", target_fixture="client")
def setup_provider(
    container: FlagdContainer, resolver_type, client_name, port
) -> OpenFeatureClient:
    try:
        container.get_exposed_port(port)
    except:  # noqa: E722
        container.start()

    path = (
        Path(__file__).parents[2] / "openfeature/test-harness/ssl/custom-root-cert.crt"
    )

    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            port=int(container.get_exposed_port(port)),
            timeout=1,
            retry_grace_period=3,
            tls=True,
            cert_path=str(path.absolute()),
        ),
        client_name,
    )
    client = api.get_client(client_name)
    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client


scenarios(
    f"{SPEC_PATH}/specification/assets/gherkin/evaluation.feature",
)
