import pytest

from openfeature.contrib.provider.flagd.config import (
    DEFAULT_DEADLINE,
    DEFAULT_HOST,
    DEFAULT_KEEP_ALIVE,
    DEFAULT_OFFLINE_SOURCE_PATH,
    DEFAULT_PORT_IN_PROCESS,
    DEFAULT_PORT_RPC,
    DEFAULT_RESOLVER_TYPE,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_STREAM_DEADLINE,
    DEFAULT_TLS,
    ENV_VAR_DEADLINE_MS,
    ENV_VAR_HOST,
    ENV_VAR_KEEP_ALIVE_TIME_MS,
    ENV_VAR_OFFLINE_FLAG_SOURCE_PATH,
    ENV_VAR_PORT,
    ENV_VAR_RESOLVER_TYPE,
    ENV_VAR_RETRY_BACKOFF_MS,
    ENV_VAR_STREAM_DEADLINE_MS,
    ENV_VAR_TLS,
    Config,
    ResolverType,
)


def test_return_default_values_rpc():
    config = Config()
    assert config.deadline == DEFAULT_DEADLINE
    assert config.host == DEFAULT_HOST
    assert config.keep_alive_time == DEFAULT_KEEP_ALIVE
    assert config.offline_flag_source_path == DEFAULT_OFFLINE_SOURCE_PATH
    assert config.port == DEFAULT_PORT_RPC
    assert config.resolver_type == DEFAULT_RESOLVER_TYPE
    assert config.retry_backoff_ms == DEFAULT_RETRY_BACKOFF
    assert config.stream_deadline_ms == DEFAULT_STREAM_DEADLINE
    assert config.tls is DEFAULT_TLS


def test_return_default_values_in_process():
    config = Config(resolver_type=ResolverType.IN_PROCESS)
    assert config.deadline == DEFAULT_DEADLINE
    assert config.host == DEFAULT_HOST
    assert config.keep_alive_time == DEFAULT_KEEP_ALIVE
    assert config.offline_flag_source_path == DEFAULT_OFFLINE_SOURCE_PATH
    assert config.port == DEFAULT_PORT_IN_PROCESS
    assert config.resolver_type == ResolverType.IN_PROCESS
    assert config.retry_backoff_ms == DEFAULT_RETRY_BACKOFF
    assert config.stream_deadline_ms == DEFAULT_STREAM_DEADLINE
    assert config.tls is DEFAULT_TLS


@pytest.fixture(params=ResolverType, scope="module")
def resolver_type(request):
    return request.param


def test_overrides_defaults_with_environment(monkeypatch, resolver_type):
    deadline = 1
    host = "flagd"
    keep_alive = 2
    offline_path = "path"
    port = 1234
    retry_backoff = 3
    stream_deadline = 4
    tls = True

    monkeypatch.setenv(ENV_VAR_DEADLINE_MS, str(deadline))
    monkeypatch.setenv(ENV_VAR_HOST, host)
    monkeypatch.setenv(ENV_VAR_KEEP_ALIVE_TIME_MS, str(keep_alive))
    monkeypatch.setenv(ENV_VAR_OFFLINE_FLAG_SOURCE_PATH, offline_path)
    monkeypatch.setenv(ENV_VAR_PORT, str(port))
    monkeypatch.setenv(ENV_VAR_RESOLVER_TYPE, str(resolver_type.value))
    monkeypatch.setenv(ENV_VAR_RETRY_BACKOFF_MS, str(retry_backoff))
    monkeypatch.setenv(ENV_VAR_STREAM_DEADLINE_MS, str(stream_deadline))
    monkeypatch.setenv(ENV_VAR_TLS, str(tls))

    config = Config()
    assert config.deadline == deadline
    assert config.host == host
    assert config.keep_alive_time == keep_alive
    assert config.offline_flag_source_path == offline_path
    assert config.port == port
    assert config.resolver_type == resolver_type
    assert config.retry_backoff_ms == retry_backoff
    assert config.stream_deadline_ms == stream_deadline
    assert config.tls is tls


def test_uses_arguments_over_environments_and_defaults(monkeypatch, resolver_type):
    deadline = 1
    host = "flagd"
    keep_alive = 2
    offline_path = "path"
    port = 1234
    retry_backoff = 3
    stream_deadline = 4
    tls = True

    monkeypatch.setenv(ENV_VAR_DEADLINE_MS, str(deadline) + "value")
    monkeypatch.setenv(ENV_VAR_HOST, host + "value")
    monkeypatch.setenv(ENV_VAR_KEEP_ALIVE_TIME_MS, str(keep_alive) + "value")
    monkeypatch.setenv(ENV_VAR_OFFLINE_FLAG_SOURCE_PATH, offline_path + "value")
    monkeypatch.setenv(ENV_VAR_PORT, str(port) + "value")
    monkeypatch.setenv(ENV_VAR_RESOLVER_TYPE, str(resolver_type) + "value")
    monkeypatch.setenv(ENV_VAR_RETRY_BACKOFF_MS, str(retry_backoff) + "value")
    monkeypatch.setenv(ENV_VAR_STREAM_DEADLINE_MS, str(stream_deadline) + "value")
    monkeypatch.setenv(ENV_VAR_TLS, str(tls) + "value")

    config = Config(
        deadline=deadline,
        host=host,
        port=port,
        resolver_type=resolver_type,
        retry_backoff_ms=retry_backoff,
        stream_deadline_ms=stream_deadline,
        tls=tls,
        keep_alive_time=keep_alive,
        offline_flag_source_path=offline_path,
    )
    assert config.deadline == deadline
    assert config.host == host
    assert config.keep_alive_time == keep_alive
    assert config.offline_flag_source_path == offline_path
    assert config.port == port
    assert config.resolver_type == resolver_type
    assert config.retry_backoff_ms == retry_backoff
    assert config.stream_deadline_ms == stream_deadline
    assert config.tls is tls
