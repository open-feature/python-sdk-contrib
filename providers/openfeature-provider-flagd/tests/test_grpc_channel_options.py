import typing
from unittest.mock import MagicMock, patch

import pytest

from openfeature.contrib.provider.flagd.config import DEFAULT_KEEP_ALIVE, Config
from openfeature.contrib.provider.flagd.resolvers.grpc import GrpcResolver
from openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher import (
    GrpcWatcher,
)

RESOLVER_CLASSES = [GrpcResolver, GrpcWatcher]


@pytest.fixture(params=RESOLVER_CLASSES, ids=["rpc", "in-process"])
def generate_channel(request):
    """Generates a grpc channel for the resolver under test and returns the
    options that were passed to grpc.insecure_channel."""
    captured: list[list[tuple[str, typing.Any]]] = []

    def fake_insecure_channel(target, options=None, **kwargs):
        captured.append(list(options or []))
        return MagicMock()

    def generate(config: Config) -> list[tuple[str, typing.Any]]:
        # `_generate_channel` only uses `config`, so the instance can be omitted.
        with patch("grpc.insecure_channel", side_effect=fake_insecure_channel):
            request.param._generate_channel(None, config)
        return captured[-1]

    return generate


def test_default_keep_alive_time_is_above_flagd_min_ping_interval(generate_channel):
    # flagd's grpc-go server enforces a MinPingInterval of 5 minutes; a more
    # frequent ping interval triggers GOAWAY (ENHANCE_YOUR_CALM, "too_many_pings").
    options = generate_channel(Config())
    assert [o for o in options if o[0] == "grpc.keepalive_time_ms"] == [
        ("grpc.keepalive_time_ms", DEFAULT_KEEP_ALIVE)
    ]
    assert DEFAULT_KEEP_ALIVE >= 5 * 60 * 1000


def test_zero_keep_alive_time_does_not_send_immediate_pings(generate_channel):
    # The gRPC C-core interprets keepalive_time_ms=0 as "send pings immediately",
    # so the option must be omitted (deferring to the gRPC default) instead.
    options = generate_channel(Config(keep_alive_time=0))
    assert all(o[0] != "grpc.keepalive_time_ms" for o in options)


def test_custom_keep_alive_time_is_passed_to_grpc(generate_channel):
    options = generate_channel(Config(keep_alive_time=10000))
    assert ("grpc.keepalive_time_ms", 10000) in options
