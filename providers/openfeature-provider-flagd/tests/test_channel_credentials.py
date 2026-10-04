from unittest.mock import Mock, mock_open, patch

import grpc
import pytest
from grpc import Channel

from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import CacheType, Config, ResolverType
from openfeature.contrib.provider.flagd.resolvers.grpc import GrpcResolver
from openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher import (
    GrpcWatcher,
)
from openfeature.contrib.provider.flagd.resolvers.process.flags import FlagStore

RPC_MODULE = "openfeature.contrib.provider.flagd.resolvers.grpc"
IN_PROCESS_MODULE = (
    "openfeature.contrib.provider.flagd.resolvers.process.connector.grpc_watcher"
)


def _make_rpc_channel(config: Config) -> Channel:
    return GrpcResolver(
        config=config,
        emit_provider_ready=Mock(),
        emit_provider_error=Mock(),
        emit_provider_stale=Mock(),
        emit_provider_configuration_changed=Mock(),
    ).channel


def _make_in_process_channel(config: Config) -> Channel:
    return GrpcWatcher(
        config=config,
        flag_store=Mock(spec=FlagStore),
        emit_provider_ready=Mock(),
        emit_provider_error=Mock(),
        emit_provider_stale=Mock(),
    ).channel


CHANNEL_FACTORIES = [
    pytest.param(RPC_MODULE, _make_rpc_channel, id="rpc"),
    pytest.param(IN_PROCESS_MODULE, _make_in_process_channel, id="in-process"),
]


@pytest.fixture
def grpc_factories(request):
    module = request.param
    with (
        patch(f"{module}.grpc.secure_channel") as secure_channel,
        patch(f"{module}.grpc.insecure_channel") as insecure_channel,
        patch(f"{module}.grpc.ssl_channel_credentials") as ssl_channel_credentials,
    ):
        yield secure_channel, insecure_channel, ssl_channel_credentials


@pytest.mark.parametrize(
    ("grpc_factories", "make_channel"), CHANNEL_FACTORIES, indirect=["grpc_factories"]
)
@pytest.mark.parametrize("tls", [False, True])
def test_custom_credentials_take_precedence(grpc_factories, make_channel, tls):
    secure_channel, insecure_channel, ssl_channel_credentials = grpc_factories
    credentials = Mock(spec=grpc.ChannelCredentials)
    config = Config(
        cache=CacheType.DISABLED,
        tls=tls,
        cert_path="/unused/server-ca.pem",
        channel_credentials=credentials,
    )

    channel = make_channel(config)

    assert channel is secure_channel.return_value
    secure_channel.assert_called_once()
    assert secure_channel.call_args.kwargs["credentials"] is credentials
    insecure_channel.assert_not_called()
    ssl_channel_credentials.assert_not_called()


@pytest.mark.parametrize(
    ("grpc_factories", "make_channel"), CHANNEL_FACTORIES, indirect=["grpc_factories"]
)
def test_tls_with_cert_path_uses_file_contents(grpc_factories, make_channel):
    secure_channel, insecure_channel, ssl_channel_credentials = grpc_factories
    config = Config(cache=CacheType.DISABLED, tls=True, cert_path="/certs/ca.pem")

    with patch("builtins.open", mock_open(read_data=b"server-ca")) as opened:
        channel = make_channel(config)

    assert channel is secure_channel.return_value
    opened.assert_called_once_with("/certs/ca.pem", "rb")
    ssl_channel_credentials.assert_called_with(b"server-ca")
    assert (
        secure_channel.call_args.kwargs["credentials"]
        is ssl_channel_credentials.return_value
    )
    insecure_channel.assert_not_called()


@pytest.mark.parametrize(
    ("grpc_factories", "make_channel"), CHANNEL_FACTORIES, indirect=["grpc_factories"]
)
def test_tls_without_cert_path_uses_default_roots(grpc_factories, make_channel):
    secure_channel, insecure_channel, ssl_channel_credentials = grpc_factories
    config = Config(cache=CacheType.DISABLED, tls=True)

    channel = make_channel(config)

    assert channel is secure_channel.return_value
    ssl_channel_credentials.assert_called_once_with()
    assert (
        secure_channel.call_args.kwargs["credentials"]
        is ssl_channel_credentials.return_value
    )
    insecure_channel.assert_not_called()


@pytest.mark.parametrize(
    ("grpc_factories", "make_channel"), CHANNEL_FACTORIES, indirect=["grpc_factories"]
)
def test_no_tls_and_no_credentials_uses_insecure_channel(grpc_factories, make_channel):
    secure_channel, insecure_channel, ssl_channel_credentials = grpc_factories
    config = Config(cache=CacheType.DISABLED, tls=False)

    channel = make_channel(config)

    assert channel is insecure_channel.return_value
    secure_channel.assert_not_called()
    ssl_channel_credentials.assert_not_called()


@pytest.mark.parametrize(
    ("resolver_type", "module"),
    [
        pytest.param(ResolverType.RPC, RPC_MODULE, id="rpc"),
        pytest.param(ResolverType.IN_PROCESS, IN_PROCESS_MODULE, id="in-process"),
    ],
)
def test_provider_forwards_custom_credentials(resolver_type, module):
    credentials = Mock(spec=grpc.ChannelCredentials)

    with (
        patch(f"{module}.grpc.secure_channel") as secure_channel,
        patch(f"{module}.grpc.insecure_channel") as insecure_channel,
    ):
        provider = FlagdProvider(
            resolver_type=resolver_type,
            tls=False,
            channel_credentials=credentials,
        )

    assert provider.config.channel_credentials is credentials
    assert secure_channel.call_args.kwargs["credentials"] is credentials
    insecure_channel.assert_not_called()
