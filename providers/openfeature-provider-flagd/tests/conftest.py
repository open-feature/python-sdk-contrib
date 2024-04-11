import os

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider


@pytest.fixture()
def flagd_provider_client():
    api.set_provider(FlagdProvider())
    return api.get_client()


def setup_flag_file(base_dir: str, flag_file: str) -> str:
    with open(f"test-harness/flags/{flag_file}") as src_file:
        contents = src_file.read()
    dst_path = os.path.join(base_dir, flag_file)
    with open(dst_path, "w") as dst_file:
        dst_file.write(contents)
    return dst_path
