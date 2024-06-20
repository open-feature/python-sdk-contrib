import time
from unittest.mock import MagicMock, patch

import pytest

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher import (
    GrpcWatcher,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import FlagStore
from openfeature.exception import ProviderNotReadyError


def fake_grpc_service(flag_config: str, keepalive: int = 100):
    def sync(request):
        mock_resp = MagicMock()
        mock_resp.flag_configuration = flag_config
        yield mock_resp
        time.sleep(keepalive)

    return sync


@pytest.mark.parametrize(
    "flag_configuration",
    (
        """{"flags": {"a-flag": {"garbage": "can"}}}""",
        """not even a JSON""",
        """{"flags": {"no-default": {"state": "ENABLED", "variants": {}}}}""",
    ),
)
def test_invalid_payload(flag_configuration: str):
    emit_provider_configuration_changed = MagicMock()
    emit_provider_ready = MagicMock()
    emit_provider_error = MagicMock()
    flag_store = FlagStore(emit_provider_configuration_changed)
    watcher = GrpcWatcher(
        Config(timeout=0.2), flag_store, emit_provider_ready, emit_provider_error
    )

    fake_sync_flags = fake_grpc_service(flag_configuration)
    with patch.object(watcher.stub, "SyncFlags", fake_sync_flags), pytest.raises(
        ProviderNotReadyError
    ):
        watcher.initialize(None)
