import threading
import time
import typing
import unittest
from unittest.mock import MagicMock, Mock, patch

from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
from grpc import Channel

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher import (
    GrpcWatcher,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import FlagStore
from openfeature.event import ProviderEventDetails
from openfeature.schemas.protobuf.flagd.sync.v1.sync_pb2 import (
    GetMetadataResponse,
    SyncFlagsResponse,
)
from openfeature.schemas.protobuf.flagd.sync.v1.sync_pb2_grpc import FlagSyncServiceStub


class TestGrpcWatcher(unittest.TestCase):
    def setUp(self):
        config = Mock(spec=Config)
        config.retry_backoff_ms = 1000
        config.retry_backoff_max_ms = 5000
        config.retry_grace_period = 5
        config.stream_deadline_ms = 1000
        config.deadline_ms = 5000
        config.selector = None
        config.provider_id = None
        config.tls = False
        config.cert_path = None
        config.channel_credentials = None
        config.host = "localhost"
        config.port = 5000
        config.sync_metadata_disabled = False

        flag_store = Mock(spec=FlagStore)
        flag_store.update.return_value = None
        emit_provider_error = Mock()
        emit_provider_stale = Mock()
        channel = Mock(spec=Channel)
        self.provider_done = False
        self.provider_details: typing.Optional[ProviderEventDetails] = None
        self.context: typing.Optional[dict] = None

        with patch(
            "openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher.GrpcWatcher._generate_channel",
            return_value=channel,
        ):
            self.grpc_watcher = GrpcWatcher(
                config=config,
                flag_store=flag_store,
                emit_provider_ready=self.provider_ready,
                emit_provider_error=emit_provider_error,
                emit_provider_stale=emit_provider_stale,
            )
        self.mock_stub = MagicMock(spec=FlagSyncServiceStub)
        self.mock_metadata = GetMetadataResponse(metadata={"attribute": "value1"})
        self.mock_stub.GetMetadata = Mock(return_value=self.mock_metadata)
        self.grpc_watcher.stub = self.mock_stub
        self.grpc_watcher.active = True

    def provider_ready(self, details: ProviderEventDetails, context: dict):
        self.provider_done = True
        self.provider_details = details
        self.context = context

    def run_listen_and_shutdown_after(self):
        listener = threading.Thread(target=self.grpc_watcher.listen)
        listener.start()
        for _i in range(0, 100):
            if self.provider_done:
                break
            time.sleep(0.001)

        self.assertTrue(self.provider_done)
        self.grpc_watcher.shutdown()
        listener.join(timeout=0.5)

    def test_listen_with_sync_metadata_and_sync_context(self):
        sync_context = Struct()
        sync_context.update({"attribute": "value"})
        mock_stream_with_sync_context = iter(
            [
                SyncFlagsResponse(
                    flag_configuration='{"flag_key": "flag_value"}',
                    sync_context=sync_context,
                ),
            ]
        )
        self.mock_stub.SyncFlags = Mock(return_value=mock_stream_with_sync_context)

        self.run_listen_and_shutdown_after()

        self.assertEqual(
            self.provider_details.message, "gRPC sync connection established"
        )
        self.assertEqual(self.context, MessageToDict(sync_context))

    def test_listen_with_sync_metadata_only(self):
        mock_stream_no_sync_context = iter(
            [
                SyncFlagsResponse(flag_configuration='{"flag_key": "flag_value"}'),
            ]
        )
        self.mock_stub.SyncFlags = Mock(return_value=mock_stream_no_sync_context)

        self.run_listen_and_shutdown_after()

        self.assertEqual(
            self.provider_details.message, "gRPC sync connection established"
        )
        self.assertEqual(self.context, MessageToDict(self.mock_metadata.metadata))

    def test_listen_with_sync_metadata_disabled_in_config(self):
        self.grpc_watcher.config.sync_metadata_disabled = True
        mock_stream_no_sync_context = iter(
            [
                SyncFlagsResponse(flag_configuration='{"flag_key": "flag_value"}'),
            ]
        )
        self.mock_stub.SyncFlags = Mock(return_value=mock_stream_no_sync_context)

        self.run_listen_and_shutdown_after()

        self.mock_stub.GetMetadata.assert_not_called()

        self.assertEqual(
            self.provider_details.message, "gRPC sync connection established"
        )
        self.assertEqual(self.context, {})
