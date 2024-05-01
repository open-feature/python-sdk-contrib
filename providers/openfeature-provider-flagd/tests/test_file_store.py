from unittest.mock import Mock

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.resolvers.process.connector.file_watcher import (
    FileWatcher,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import Flag, FlagStore
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
def test_file_load(file_name: str):
    provider = Mock(spec=AbstractProvider)
    flag_store = FlagStore(provider)
    file_watcher = FileWatcher(f"tests/flags/{file_name}", provider, flag_store)
    file_watcher.initialize(None)

    flag = flag_store.get_flag("basic-flag")

    assert flag is not None
    assert isinstance(flag, Flag)
