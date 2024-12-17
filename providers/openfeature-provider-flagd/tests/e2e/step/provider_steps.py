import logging
import threading

import pytest
from pytest_bdd import given, parsers, when
from testcontainers.core.container import DockerContainer
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.step._utils import wait_for

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus


@given("a provider is registered", target_fixture="client")
def setup_provider_old(
    container: FlagdContainer,
    resolver_type: ResolverType,
    option_values: dict,
) -> OpenFeatureClient:
    setup_provider(container, resolver_type, "stable", dict)


@given(parsers.cfparse("a {provider_type} flagd provider"), target_fixture="client")
def setup_provider(
    container: FlagdContainer,
    resolver_type: ResolverType,
    provider_type: str,
    option_values: dict,
) -> OpenFeatureClient:
    if provider_type == "unavailable":
        api.set_provider(
            FlagdProvider(
                resolver_type=resolver_type,
                **option_values,
            ),
            "unavailable",
        )
        client = api.get_client("unavailable")
        return client

    try:
        container.get_port(resolver_type)
    except:  # noqa: E722
        container.start()
    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            port=container.get_port(resolver_type),
            deadline_ms=500,
            stream_deadline_ms=0,
            retry_backoff_ms=1000,
            **option_values,
        ),
        provider_type,
    )
    client = api.get_client(provider_type)

    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client


@when(parsers.cfparse("the connection is lost for {seconds}s"))
def flagd_restart(seconds, container: FlagdContainer):
    ipr_port = container.get_port(ResolverType.IN_PROCESS)
    rpc_port = container.get_port(ResolverType.RPC)

    def starting():
        container.with_bind_ports(8015, ipr_port)
        container.with_bind_ports(8013, rpc_port)
        container.start()

    restart_timer = threading.Timer(interval=int(seconds), function=starting)
    restart_timer.start()
    container.stop()


@pytest.fixture(autouse=True, scope="module")
def container(request):
    container: DockerContainer = FlagdContainer()

    # Setup code
    container.start()

    def fin():
        try:
            container.stop()
        except:  # noqa: E722
            logging.debug("container was not running anymore")

    # Teardown code
    request.addfinalizer(fin)

    return container
