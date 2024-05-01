import os
from pathlib import Path

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider


@pytest.fixture()
def flagd_provider_client():
    provider = FlagdProvider()
    api.set_provider(provider)
    yield api.get_client()
    provider.shutdown()


def setup_flag_file(base_dir: str, flag_file: str) -> str:
    contents = (Path(__file__).parent / "../test-harness/flags" / flag_file).read_text()
    dst_path = os.path.join(base_dir, flag_file)
    with open(dst_path, "w") as dst_file:
        dst_file.write(contents)
    return dst_path
