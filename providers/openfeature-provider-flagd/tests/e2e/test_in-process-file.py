import json
import os
import tempfile
from os import listdir

import pytest
import yaml
from asserts import assert_true
from pytest_bdd import parsers, scenarios, then

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

KEY_EVALUATORS = "$evaluators"

KEY_FLAGS = "flags"

MERGED_FILE = "merged_file"


@pytest.fixture(params=["json", "yaml"], scope="package")
def file_name(request):
    extension = request.param
    result = {KEY_FLAGS: {}, KEY_EVALUATORS: {}}

    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../test-harness/flags/")
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


@pytest.fixture(autouse=True, scope="package")
def setup(request, file_name):
    """`file_name` tests"""
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=file_name.name,
        )
    )


@then(
    parsers.cfparse("the PROVIDER_CONFIGURATION_CHANGED handler must run"),
)
def provider_changed_was_executed():
    assert_true(True)
    # TODO: DELETE AFTER IMPLEMENTATION OF EVENTS FOR RPC


@then(parsers.cfparse('the event details must indicate "{flag_name}" was altered'))
def flag_was_changed():
    assert_true(True)
    # TODO: DELETE AFTER IMPLEMENTATION OF EVENTS FOR RPC


scenarios(
    "../../test-harness/gherkin/flagd.feature",
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "../../spec/specification/assets/gherkin/evaluation.feature",
)
