import json
import os
import tempfile
from os import listdir

import pytest
import yaml
from pytest_bdd import given, scenario, scenarios
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


@pytest.fixture(params=["json", "yaml"], scope="module")
def file_name(request):
    extension = request.param
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

    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix="." + extension
    ) as outfile:
        if extension == "json":
            json.dump(result, outfile)
        else:
            yaml.dump(result, outfile)

    return outfile


@pytest.fixture(autouse=True, scope="module")
def client_name() -> str:
    return "in-process"


@pytest.fixture(autouse=True, scope="module")
def resolver_type() -> ResolverType:
    return ResolverType.IN_PROCESS


@pytest.fixture(autouse=True, scope="module")
def setup(request, client_name, file_name, resolver_type):
    """nothing to boot"""
    api.set_provider(
        FlagdProvider(
            resolver_type=resolver_type,
            offline_flag_source_path=file_name.name,
        ),
        client_name,
    )


@given("a flagd provider is set", target_fixture="client")
@given("a provider is registered", target_fixture="client")
def setup_provider(client_name) -> OpenFeatureClient:
    client = api.get_client(client_name)
    wait_for(lambda: client.get_provider_status() == ProviderStatus.READY)
    return client


@pytest.mark.skip(reason="Eventing not implemented")
@scenario(f"{TEST_HARNESS_PATH}/gherkin/flagd.feature", "Flag change event")
def test_flag_change_event():
    """not implemented"""


scenarios(
    f"{TEST_HARNESS_PATH}/gherkin/flagd.feature",
    f"{TEST_HARNESS_PATH}/gherkin/flagd-json-evaluator.feature",
    f"{SPEC_PATH}/specification/assets/gherkin/evaluation.feature",
)
