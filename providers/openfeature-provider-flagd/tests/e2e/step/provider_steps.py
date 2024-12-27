import logging
import threading
import typing
from enum import Enum
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, when
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.step._offline import *  # noqa: F403
from tests.e2e.step._utils import wait_for

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus


class TestProviderType(Enum):
    UNAVAILABLE = "unavailable"
    STABLE = "stable"
    UNSTABLE = "unstable"
    SSL = "ssl"
    SOCKET = "socket"
    OFFLINE = "offline"


@given("a provider is registered", target_fixture="client")
def setup_provider_old(
    container: FlagdContainer,
    resolver_type: ResolverType,
    option_values: dict,
) -> OpenFeatureClient:
    setup_provider(container, resolver_type, "stable", dict)


def get_default_options_for_provider(
    provider_type: str, resolver_type: ResolverType, file_name
) -> typing.Tuple[dict, bool]:
    t = TestProviderType(provider_type)
    options: dict = {
        "resolver_type": resolver_type,
        "deadline_ms": 500,
        "stream_deadline_ms": 0,
        "retry_backoff_ms": 1000,
        "retry_grace_period": 2,
    }

    if t == TestProviderType.UNAVAILABLE:
        return {}, False
    elif t == TestProviderType.SSL:
        path = (
            Path(__file__).parents[3]
            / "openfeature/test-harness/ssl/custom-root-cert.crt"
        )
        options["cert_path"] = str(path.absolute())
        options["tls"] = True
    elif t == TestProviderType.SOCKET:
        return options, True
    elif t == TestProviderType.OFFLINE or resolver_type == ResolverType.IN_PROCESS:
        options["offline_flag_source_path"] = file_name.name
        return options, True

    return options, True


@given(
    parsers.cfparse("a {provider_type} flagd provider"), target_fixture="provider_type"
)
def setup_provider(
    containers: dict,
    resolver_type: ResolverType,
    provider_type: str,
    option_values: dict,
    file_name,
) -> OpenFeatureClient:
    default_options, ready = get_default_options_for_provider(
        provider_type, resolver_type, file_name
    )

    if ready:
        container = (
            containers.get(provider_type)
            if provider_type in containers
            else containers.get("default")
        )
        try:
            container.get_port(resolver_type)
        except:  # noqa: E722
            container.start()

        default_options["port"] = container.get_port(resolver_type)

    combined_options = {**default_options, **option_values}
    api.set_provider(
        FlagdProvider(**combined_options),
        provider_type,
    )
    client = api.get_client(provider_type)

    wait_for(
        lambda: client.get_provider_status() == ProviderStatus.READY
    ) if ready else None
    return provider_type


@pytest.fixture()
def client(provider_type: str) -> OpenFeatureClient:
    return api.get_client(provider_type)


@when(parsers.cfparse("the connection is lost for {seconds}s"))
def flagd_restart(
    seconds,
    containers: dict,
    provider_type: str,
    resolver_type: ResolverType,
    file_name,
):
    if resolver_type == ResolverType.IN_PROCESS:
        old_name = Path(file_name.name)
        new_name = Path(file_name.name + "-deactivated")

        def starting():
            new_name.rename(old_name)

        restart_timer = threading.Timer(interval=int(seconds), function=starting)
        restart_timer.start()
        if old_name.exists():
            old_name.rename(new_name)

    else:
        container = (
            containers.get(provider_type)
            if provider_type in containers
            else containers.get("default")
        )
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
def containers(request):
    containers = {
        "default": FlagdContainer(),
        "ssl": FlagdContainer("ssl"),
    }

    [containers[c].start() for c in containers]

    def fin():
        for name, container in containers.items():
            try:
                container.stop()
            except:  # noqa: E722, PERF203 - we want to ensure all containers are stopped, even if we do have an exception here
                logging.debug(f"container '{name}' was not running anymore")

    # Teardown code
    request.addfinalizer(fin)

    return containers
