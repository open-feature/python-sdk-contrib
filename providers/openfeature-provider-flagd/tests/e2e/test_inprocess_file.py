import json
import os
import tempfile
from os import listdir

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, when
from tests.e2e.conftest import SPEC_PATH, TEST_HARNESS_PATH
from tests.e2e.steps import wait_for

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.provider import ProviderStatus

KEY_EVALUATORS = "$evaluators"

KEY_FLAGS = "flags"

MERGED_FILE = "merged_file"


@pytest.fixture(scope="module")
def all_flags(request):
    result = {KEY_FLAGS: {}, KEY_EVALUATORS: {}}

    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), f"{TEST_HARNESS_PATH}/flags/")
    )

    for f in listdir(path):
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


@pytest.fixture(autouse=True, scope="module")
def resolver_type() -> ResolverType:
    return ResolverType.IN_PROCESS


@pytest.fixture(autouse=True, scope="module")
def client_name() -> str:
    return "in-process-file"


@pytest.fixture(autouse=True, scope="module")
def setup(request, client_name, file_name, resolver_type):
    """nothing to boot"""
    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            offline_flag_source_path=file_name.name,
            deadline=500,
            retry_backoff_ms=100,
        ),
        client_name,
    )


@given("a flagd provider is set", target_fixture="client")
@given("a provider is registered", target_fixture="client")
def setup_provider(client_name) -> OpenFeatureClient:
    client = api.get_client(client_name)
    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client


scenarios(
    f"{TEST_HARNESS_PATH}/gherkin/flagd.feature",
    f"{TEST_HARNESS_PATH}/gherkin/flagd-json-evaluator.feature",
    f"{SPEC_PATH}/specification/assets/gherkin/evaluation.feature",
)
