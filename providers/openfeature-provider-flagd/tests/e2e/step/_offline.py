import json
import logging
import os
import tempfile
import threading
import time

import pytest
import yaml
from e2e.conftest import TEST_HARNESS_PATH

KEY_EVALUATORS = "$evaluators"

KEY_FLAGS = "flags"

MERGED_FILE = "merged_file"


# Everything below here, should be actually part of the provider steps - for now it is just easier this way


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


@pytest.fixture(params=["json", "yaml"], scope="module", autouse=True)
def file_name(request, all_flags):
    extension = request.param
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
