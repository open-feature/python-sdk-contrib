from unittest.mock import Mock

import pytest
from src.openfeature.contrib.provider.flagd.resolvers.process.file_watcher import (
    FileWatcherFlagStore,
)
from src.openfeature.contrib.provider.flagd.resolvers.process.flags import Flag

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.provider.provider import AbstractProvider


def create_client(provider: FlagdProvider):
    api.set_provider(provider)
    return api.get_client()


@pytest.mark.parametrize(
    "file_name",
    [
        "basic-flag.json",
        "basic-flag.yaml",
    ],
)
def test_file_load_errors(file_name: str):
    provider = Mock(spec=AbstractProvider)
    file_store = FileWatcherFlagStore(f"tests/flags/{file_name}", provider)

    flag = file_store.flag_data.get("basic-flag")

    assert flag is not None
    assert isinstance(flag, Flag)
