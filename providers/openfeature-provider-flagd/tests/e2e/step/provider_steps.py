import json
import logging
import os
import tempfile
import threading
import time
import typing
from enum import Enum
from pathlib import Path

import pytest
import requests
import yaml
from pytest_bdd import given, parsers, when
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.paths import TEST_HARNESS_PATH
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
    provider_type: str, resolver_type: ResolverType, file_name, container
) -> typing.Tuple[dict, bool]:
    launchpad = "default"
    t = TestProviderType(provider_type)
    options: dict = {
        "resolver_type": resolver_type,
        "deadline_ms": 500,
        "stream_deadline_ms": 0,
        "retry_backoff_ms": 1000,
        "retry_grace_period": 2,
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
        options["offline_flag_source_path"] = file_name.name

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
    file_name,
) -> OpenFeatureClient:
    default_options, wait = get_default_options_for_provider(
        provider_type, resolver_type, file_name, container
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
    file_name,
):
    if resolver_type == ResolverType.FILE:
        old_name = Path(file_name.name)
        new_name = Path(file_name.name + "-deactivated")

        def starting():
            new_name.rename(old_name)

        restart_timer = threading.Timer(interval=int(seconds), function=starting)
        restart_timer.start()
        if old_name.exists():
            old_name.rename(new_name)

    else:
        requests.post(
            f"{container.get_launchpad_url()}/restart?seconds={seconds}", timeout=1
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


@pytest.fixture(scope="module", autouse=True)
def all_flags(request):
    result = {KEY_FLAGS: {}, KEY_EVALUATORS: {}}

    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"../{TEST_HARNESS_PATH}/flags/")
    )

    for f in os.listdir(path):
        with open(path + "/" + f, "rb") as infile:
            loaded_json = json.load(infile)
            result[KEY_FLAGS] = {**result[KEY_FLAGS], **loaded_json[KEY_FLAGS]}
            if loaded_json.get(KEY_EVALUATORS):
                result[KEY_EVALUATORS] = {
                    **result[KEY_EVALUATORS],
                    **loaded_json[KEY_EVALUATORS],
                }

    return result


@pytest.fixture(scope="module", autouse=True)
def file_name(request, all_flags):
    extension = "json"
    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix="." + extension
    ) as outfile:
        write_test_file(outfile, all_flags)

        update_thread = threading.Thread(
            target=changefile, args=("changing-flag", all_flags, outfile)
        )
        update_thread.daemon = True  # Makes the thread exit when the main program exits
        update_thread.start()
        yield outfile
        return outfile


def write_test_file(outfile, all_flags):
    with open(outfile.name, "w") as file:
        if file.name.endswith("json"):
            json.dump(all_flags, file)
        else:
            yaml.dump(all_flags, file)


def changefile(
    flag_key: str,
    all_flags: dict,
    file_name,
):
    while True:
        if not os.path.exists(file_name.name):
            continue

        flag = all_flags[KEY_FLAGS][flag_key]

        other_variant = [
            k for k in flag["variants"] if flag["defaultVariant"] in k
        ].pop()

        flag["defaultVariant"] = other_variant

        all_flags[KEY_FLAGS][flag_key] = flag
        write_test_file(file_name, all_flags)
        logging.warn("changing flags")
        time.sleep(5)
