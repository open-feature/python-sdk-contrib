import json
import os
import tempfile

import pytest
import yaml
from pytest_bdd import given, parsers, when
from tests.e2e.conftest import TEST_HARNESS_PATH
from tests.e2e.step._utils import wait_for
from tests.e2e.testFilter import TestFilter

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus

# from tests.e2e.step.config_steps import *
# from tests.e2e.step.event_steps import *
# from tests.e2e.step.provider_steps import *

resolver = ResolverType.IN_PROCESS
feature_list = {
    "~targetURI",
    "~customCert",
    "~unixsocket",
    "~events",
    "~sync",
    "~caching",
    "~reconnect",
    "~grace",
}


def pytest_collection_modifyitems(config, items):
    test_filter = TestFilter(
        config, feature_list=feature_list, resolver=resolver.value, base_path=__file__
    )
    test_filter.filter_items(items)


KEY_EVALUATORS = "$evaluators"

KEY_FLAGS = "flags"

MERGED_FILE = "merged_file"


@pytest.fixture()
def resolver_type() -> ResolverType:
    return resolver


@pytest.fixture(scope="module")
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


@pytest.fixture(params=["json", "yaml"], scope="module")
def file_name(request, all_flags):
    extension = request.param
    outfile = tempfile.NamedTemporaryFile("w", delete=False, suffix="." + extension)
    write_test_file(outfile, all_flags)
    yield outfile
    return outfile


def write_test_file(outfile, all_flags):
    with open(outfile.name, "w") as file:
        if file.name.endswith("json"):
            json.dump(all_flags, file)
        else:
            yaml.dump(all_flags, file)


@when(
    parsers.cfparse('a flag with key "{flag_key}" is modified'),
    target_fixture="changed_flag",
)
def changed_flag(
    flag_key: str,
    all_flags: dict,
    file_name,
):
    flag = all_flags[KEY_FLAGS][flag_key]

    other_variant = [k for k in flag["variants"] if flag["defaultVariant"] in k].pop()

    flag["defaultVariant"] = other_variant

    all_flags[KEY_FLAGS][flag_key] = flag
    write_test_file(file_name, all_flags)
    return flag_key


@pytest.fixture(autouse=True)
def container(request, file_name, all_flags, option_values):
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            deadline_ms=500,
            stream_deadline_ms=0,
            retry_backoff_ms=1000,
            offline_flag_source_path=file_name.name,
            **option_values,
        ),
    )
    pass


@given(parsers.cfparse("a {provider_type} flagd provider"), target_fixture="client")
def setup_provider(
    resolver_type: ResolverType, provider_type: str, option_values: dict, file_name
) -> OpenFeatureClient:
    client = api.get_client()

    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client
