import unittest
from unittest.mock import MagicMock, Mock, patch

import grpc
from grpc import Channel

from openfeature.contrib.provider.flagd.config import CacheType, Config
from openfeature.contrib.provider.flagd.flag_type import FlagType
from openfeature.contrib.provider.flagd.resolvers.grpc import (
    FLAGD_SELECTOR_HEADER,
    GrpcResolver,
)
from openfeature.schemas.protobuf.flagd.evaluation.v2 import evaluation_pb2


class FakeRpcError(grpc.RpcError):
    def code(self):
        return grpc.StatusCode.UNAVAILABLE

    def details(self):
        return "stream unavailable"


def _make_resolver(selector):
    config = Config(host="localhost", port=8013, tls=False)
    config.selector = selector
    resolver = GrpcResolver(
        config=config,
        emit_provider_ready=Mock(),
        emit_provider_error=Mock(),
        emit_provider_stale=Mock(),
        emit_provider_configuration_changed=Mock(),
    )
    return resolver


def test_unary_call_includes_selector_metadata_when_configured():
    resolver = _make_resolver("test-selector")
    mock_stub = MagicMock()
    mock_stub.ResolveBoolean = Mock(
        return_value=evaluation_pb2.ResolveBooleanResponse(value=True, reason="STATIC")
    )
    resolver.stub = mock_stub

    resolver._resolve("flag", FlagType.BOOLEAN, False, None)

    kwargs = mock_stub.ResolveBoolean.call_args.kwargs
    assert kwargs.get("metadata") == ((FLAGD_SELECTOR_HEADER, "test-selector"),)


def test_unary_call_omits_metadata_when_no_selector():
    resolver = _make_resolver(None)
    mock_stub = MagicMock()
    mock_stub.ResolveBoolean = Mock(
        return_value=evaluation_pb2.ResolveBooleanResponse(value=True, reason="STATIC")
    )
    resolver.stub = mock_stub

    resolver._resolve("flag", FlagType.BOOLEAN, False, None)

    kwargs = mock_stub.ResolveBoolean.call_args.kwargs
    assert "metadata" not in kwargs


def test_event_stream_includes_selector_metadata_when_configured():
    resolver = _make_resolver("test-selector")
    mock_stub = MagicMock()

    def stop_after_call(*args, **kwargs):
        resolver.active = False
        return iter(())

    mock_stub.EventStream = Mock(side_effect=stop_after_call)
    resolver.stub = mock_stub
    resolver.active = True

    resolver.listen()

    kwargs = mock_stub.EventStream.call_args.kwargs
    assert kwargs.get("metadata") == ((FLAGD_SELECTOR_HEADER, "test-selector"),)


def test_event_stream_omits_metadata_when_no_selector():
    resolver = _make_resolver(None)
    mock_stub = MagicMock()

    def stop_after_call(*args, **kwargs):
        resolver.active = False
        return iter(())

    mock_stub.EventStream = Mock(side_effect=stop_after_call)
    resolver.stub = mock_stub
    resolver.active = True

    resolver.listen()

    kwargs = mock_stub.EventStream.call_args.kwargs
    assert "metadata" not in kwargs


class TestGrpcResolver(unittest.TestCase):
    def setUp(self):
        config = Config(
            cache=CacheType.DISABLED,
            deadline_ms=100,
            retry_backoff_ms=1000,
            retry_backoff_max_ms=5000,
            stream_deadline_ms=1000,
        )
        channel = Mock(spec=Channel)

        with patch(
            "openfeature.contrib.provider.flagd.resolvers.grpc.GrpcResolver._generate_channel",
            return_value=channel,
        ):
            self.emit_provider_ready = Mock()
            self.emit_provider_error = Mock()
            self.emit_provider_stale = Mock()
            self.grpc_resolver = GrpcResolver(
                config=config,
                emit_provider_ready=self.emit_provider_ready,
                emit_provider_error=self.emit_provider_error,
                emit_provider_stale=self.emit_provider_stale,
                emit_provider_configuration_changed=Mock(),
            )

        self.grpc_resolver.stub = MagicMock()
        self.grpc_resolver.active = True

    def test_uses_max_retry_backoff_for_application_level_reconnect_delay(self):
        self.assertEqual(self.grpc_resolver.retry_backoff_max_seconds, 5)

    def test_nonfatal_rpc_stream_errors_mark_stale_and_back_off(self):
        self.grpc_resolver.stub.EventStream = Mock(side_effect=FakeRpcError())
        self.grpc_resolver.connected = True

        with (
            patch.object(
                self.grpc_resolver,
                "_wait_before_reconnect",
                side_effect=lambda: setattr(self.grpc_resolver, "active", False),
            ) as wait_before_reconnect,
            patch(
                "openfeature.contrib.provider.flagd.resolvers.grpc.threading.Timer"
            ) as timer_class,
        ):
            self.grpc_resolver.listen()

        wait_before_reconnect.assert_called_once()
        self.assertFalse(self.grpc_resolver.connected)
        self.emit_provider_stale.assert_called_once()
        timer_class.assert_called_once_with(
            self.grpc_resolver.retry_grace_period, self.grpc_resolver.emit_error
        )
        timer_class.return_value.start.assert_called_once()

    def test_listen_backs_off_after_stream_completion(self):
        self.grpc_resolver.stub.EventStream = Mock(return_value=iter([]))

        with patch.object(
            self.grpc_resolver,
            "_wait_before_reconnect",
            side_effect=lambda: setattr(self.grpc_resolver, "active", False),
        ) as wait_before_reconnect:
            self.grpc_resolver.listen()

        wait_before_reconnect.assert_called_once()

    def test_unexpected_stream_errors_mark_stale_and_keep_one_grace_timer(self):
        self.grpc_resolver.stub.EventStream = Mock(
            side_effect=RuntimeError("interceptor failed")
        )
        self.grpc_resolver.connected = True
        wait_count = 0

        def stop_after_two_retries():
            nonlocal wait_count
            wait_count += 1
            if wait_count == 2:
                self.grpc_resolver.active = False

        with (
            patch.object(
                self.grpc_resolver,
                "_wait_before_reconnect",
                side_effect=stop_after_two_retries,
            ) as wait_before_reconnect,
            patch(
                "openfeature.contrib.provider.flagd.resolvers.grpc.threading.Timer"
            ) as timer_class,
        ):
            self.grpc_resolver.listen()

        self.assertEqual(wait_before_reconnect.call_count, 2)
        self.assertFalse(self.grpc_resolver.connected)
        self.emit_provider_stale.assert_called_once()
        timer_class.assert_called_once_with(
            self.grpc_resolver.retry_grace_period, self.grpc_resolver.emit_error
        )
        timer_class.return_value.start.assert_called_once()
        timer_class.call_args.args[1]()
        self.emit_provider_error.assert_called_once()

    def test_provider_ready_cancels_event_stream_error_timer(self):
        timer = Mock()
        self.grpc_resolver.timer = timer

        self.grpc_resolver._handle_event_stream_message(
            evaluation_pb2.EventStreamResponse(type="provider_ready")
        )

        timer.cancel.assert_called_once()
        self.assertIsNone(self.grpc_resolver.timer)
        self.assertTrue(self.grpc_resolver.connected)
        self.emit_provider_ready.assert_called_once()

    def test_generate_channel_applies_client_interceptors(self):
        interceptor = Mock(spec=grpc.UnaryUnaryClientInterceptor)
        raw_channel = Mock(spec=Channel)
        wrapped_channel = Mock(spec=Channel)
        config = Config(
            tls=False, cache=CacheType.DISABLED, client_interceptors=[interceptor]
        )

        with (
            patch(
                "openfeature.contrib.provider.flagd.resolvers.grpc.grpc.insecure_channel",
                return_value=raw_channel,
            ),
            patch(
                "openfeature.contrib.provider.flagd.config.grpc.intercept_channel",
                return_value=wrapped_channel,
            ) as intercept_channel,
        ):
            resolver = GrpcResolver(
                config=config,
                emit_provider_ready=Mock(),
                emit_provider_error=Mock(),
                emit_provider_stale=Mock(),
                emit_provider_configuration_changed=Mock(),
            )

        self.assertIs(resolver.channel, wrapped_channel)
        intercept_channel.assert_called_once_with(raw_channel, interceptor)

    def test_generate_channel_skips_intercept_channel_when_no_interceptors(self):
        raw_channel = Mock(spec=Channel)
        config = Config(tls=False, cache=CacheType.DISABLED)

        with (
            patch(
                "openfeature.contrib.provider.flagd.resolvers.grpc.grpc.insecure_channel",
                return_value=raw_channel,
            ),
            patch(
                "openfeature.contrib.provider.flagd.config.grpc.intercept_channel",
            ) as intercept_channel,
        ):
            resolver = GrpcResolver(
                config=config,
                emit_provider_ready=Mock(),
                emit_provider_error=Mock(),
                emit_provider_stale=Mock(),
                emit_provider_configuration_changed=Mock(),
            )

        self.assertIs(resolver.channel, raw_channel)
        intercept_channel.assert_not_called()


if __name__ == "__main__":
    unittest.main()
