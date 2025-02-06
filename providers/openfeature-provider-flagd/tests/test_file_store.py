import os
from unittest.mock import Mock

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.process.connector.file_watcher import (
    FileWatcher,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import Flag, FlagStore


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
    emit_provider_configuration_changed = Mock()
    emit_provider_ready = Mock()
    emit_provider_error = Mock()
    flag_store = FlagStore(emit_provider_configuration_changed)
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "./flags/"))
    file_watcher = FileWatcher(
        Config(
            offline_flag_source_path=f"{path}/{file_name}",
        ),
        flag_store,
        emit_provider_ready,
        emit_provider_error,
    )
    file_watcher.initialize(None)

    flag = flag_store.get_flag("basic-flag")

    assert flag is not None
    assert isinstance(flag, Flag)
