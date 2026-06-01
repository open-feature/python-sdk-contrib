from contextlib import suppress
from unittest.mock import MagicMock, Mock

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.flag_type import FlagType
from openfeature.contrib.provider.flagd.resolvers.grpc import (
    FLAGD_SELECTOR_HEADER,
    GrpcResolver,
)
from openfeature.schemas.protobuf.flagd.evaluation.v2 import evaluation_pb2


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
    mock_stub.EventStream = Mock(side_effect=Exception("break loop"))
    resolver.stub = mock_stub
    resolver.active = True

    with suppress(Exception):
        resolver.listen()

    kwargs = mock_stub.EventStream.call_args.kwargs
    assert kwargs.get("metadata") == ((FLAGD_SELECTOR_HEADER, "test-selector"),)


def test_event_stream_omits_metadata_when_no_selector():
    resolver = _make_resolver(None)
    mock_stub = MagicMock()
    mock_stub.EventStream = Mock(side_effect=Exception("break loop"))
    resolver.stub = mock_stub
    resolver.active = True

    with suppress(Exception):
        resolver.listen()

    kwargs = mock_stub.EventStream.call_args.kwargs
    assert "metadata" not in kwargs
