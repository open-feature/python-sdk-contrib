import logging
import os
import time
from enum import Enum
from pathlib import Path

import pytest
import requests
from pytest_bdd import given, parsers, when
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.step._utils import wait_for

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus

KEY_EVALUATORS = "$evaluators"

KEY_FLAGS = "flags"

MERGED_FILE = "merged_file"


class TestProviderType(Enum):
    UNAVAILABLE = "unavailable"
    STABLE = "stable"
    UNSTABLE = "unstable"
    SSL = "ssl"
    SOCKET = "socket"


@given("a provider is registered", target_fixture="client")
def setup_provider_old(
    container: FlagdContainer,
    resolver_type: ResolverType,
    option_values: dict,
) -> OpenFeatureClient:
    setup_provider(container, resolver_type, "stable", dict)


def get_default_options_for_provider(
    provider_type: str, resolver_type: ResolverType, container
) -> tuple[dict, bool]:
    launchpad = "default"
    t = TestProviderType(provider_type)
    options: dict = {
        "resolver_type": resolver_type,
        "deadline_ms": 1000,
        "stream_deadline_ms": 0,
        "retry_backoff_ms": 1000,
        "retry_grace_period": 3,
        "port": container.get_port(resolver_type),
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
        launchpad = "ssl"
    elif t == TestProviderType.SOCKET:
        return options, True

    if resolver_type == ResolverType.FILE:
        options["offline_flag_source_path"] = os.path.join(
            container.flagDir.name, "allFlags.json"
        )

    requests.post(
        f"{container.get_launchpad_url()}/start?config={launchpad}", timeout=1
    )
    time.sleep(0.1)
    return options, True


@given(
    parsers.cfparse("a {provider_type} flagd provider"), target_fixture="provider_type"
)
def setup_provider(
    container: FlagdContainer,
    resolver_type: ResolverType,
    provider_type: str,
    option_values: dict,
) -> OpenFeatureClient:
    default_options, wait = get_default_options_for_provider(
        provider_type, resolver_type, container
    )

    combined_options = {**default_options, **option_values}
    api.set_provider(
        FlagdProvider(**combined_options),
        provider_type,
    )
    client = api.get_client(provider_type)

    wait_for(
        lambda: client.get_provider_status() == ProviderStatus.READY
    ) if wait else None
    return provider_type


@pytest.fixture()
def client(provider_type: str) -> OpenFeatureClient:
    return api.get_client(provider_type)


@when(parsers.cfparse("the connection is lost for {seconds}s"))
def flagd_restart(
    seconds,
    container: FlagdContainer,
    provider_type: str,
    resolver_type: ResolverType,
):
    requests.post(
        f"{container.get_launchpad_url()}/restart?seconds={seconds}", timeout=2
    )
    pass


@pytest.fixture(autouse=True, scope="package")
def container(request):
    container = FlagdContainer()

    container.start()

    def fin():
        try:
            container.stop()
        except:  # noqa: E722 - we want to ensure all containers are stopped, even if we do have an exception here
            logging.debug("container was not running anymore")

    # Teardown code
    request.addfinalizer(fin)

    return container
