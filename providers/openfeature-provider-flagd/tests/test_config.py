import pytest

# not sure if we still need this test, as this is also covered with gherkin tests.
from openfeature.contrib.provider.flagd.config import (
    DEFAULT_CACHE,
    DEFAULT_CACHE_SIZE,
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
    ENV_VAR_CACHE_SIZE,
    ENV_VAR_CACHE_TYPE,
    ENV_VAR_DEADLINE_MS,
    ENV_VAR_HOST,
    ENV_VAR_KEEP_ALIVE_TIME_MS,
    ENV_VAR_OFFLINE_FLAG_SOURCE_PATH,
    ENV_VAR_PORT,
    ENV_VAR_RETRY_BACKOFF_MS,
    ENV_VAR_STREAM_DEADLINE_MS,
    ENV_VAR_TLS,
    CacheType,
    Config,
    ResolverType,
)


def test_return_default_values_rpc():
    config = Config()
    assert config.cache == DEFAULT_CACHE
    assert config.max_cache_size == DEFAULT_CACHE_SIZE
    assert config.deadline_ms == DEFAULT_DEADLINE
    assert config.host == DEFAULT_HOST
    assert config.keep_alive_time == DEFAULT_KEEP_ALIVE
    assert config.offline_flag_source_path == DEFAULT_OFFLINE_SOURCE_PATH
    assert config.port == DEFAULT_PORT_RPC
    assert config.resolver == DEFAULT_RESOLVER_TYPE
    assert config.retry_backoff_ms == DEFAULT_RETRY_BACKOFF
    assert config.stream_deadline_ms == DEFAULT_STREAM_DEADLINE
    assert config.tls is DEFAULT_TLS


def test_return_default_values_in_process():
    config = Config(resolver=ResolverType.IN_PROCESS)
    assert config.cache == DEFAULT_CACHE
    assert config.max_cache_size == DEFAULT_CACHE_SIZE
    assert config.deadline_ms == DEFAULT_DEADLINE
    assert config.host == DEFAULT_HOST
    assert config.keep_alive_time == DEFAULT_KEEP_ALIVE
    assert config.offline_flag_source_path == DEFAULT_OFFLINE_SOURCE_PATH
    assert config.port == DEFAULT_PORT_IN_PROCESS
    assert config.resolver == ResolverType.IN_PROCESS
    assert config.retry_backoff_ms == DEFAULT_RETRY_BACKOFF
    assert config.stream_deadline_ms == DEFAULT_STREAM_DEADLINE
    assert config.tls is DEFAULT_TLS


@pytest.fixture(params=ResolverType, scope="module")
def resolver_type(request):
    return request.param


def test_overrides_defaults_with_environment(monkeypatch, resolver_type):  # noqa: PLR0915
    cache = CacheType.DISABLED
    cache_size = 456
    deadline = 1
    host = "flagd"
    keep_alive = 2
    offline_path = "path"
    port = 1234
    retry_backoff = 3
    stream_deadline = 4
    tls = True

    monkeypatch.setenv(ENV_VAR_CACHE_TYPE, str(cache.value))
    monkeypatch.setenv(ENV_VAR_CACHE_SIZE, str(cache_size))
    monkeypatch.setenv(ENV_VAR_DEADLINE_MS, str(deadline))
    monkeypatch.setenv(ENV_VAR_HOST, host)
    monkeypatch.setenv(ENV_VAR_KEEP_ALIVE_TIME_MS, str(keep_alive))
    monkeypatch.setenv(ENV_VAR_OFFLINE_FLAG_SOURCE_PATH, offline_path)
    monkeypatch.setenv(ENV_VAR_PORT, str(port))
    monkeypatch.setenv(ENV_VAR_RETRY_BACKOFF_MS, str(retry_backoff))
    monkeypatch.setenv(ENV_VAR_STREAM_DEADLINE_MS, str(stream_deadline))
    monkeypatch.setenv(ENV_VAR_TLS, str(tls))

    config = Config()
    assert config.cache == cache
    assert config.max_cache_size == cache_size
    assert config.deadline_ms == deadline
    assert config.host == host
    assert config.keep_alive_time == keep_alive
    assert config.offline_flag_source_path == offline_path
    assert config.port == port
    assert config.retry_backoff_ms == retry_backoff
    assert config.stream_deadline_ms == stream_deadline
    assert config.tls is tls


def test_uses_arguments_over_environments_and_defaults(monkeypatch, resolver_type):  # noqa: PLR0915
    cache = CacheType.LRU
    cache_size = 456
    deadline = 1
    host = "flagd"
    keep_alive = 2
    offline_path = "path"
    port = 1234
    retry_backoff = 3
    stream_deadline = 4
    tls = True

    monkeypatch.setenv(ENV_VAR_CACHE_TYPE, str(cache.value) + "value")
    monkeypatch.setenv(ENV_VAR_CACHE_SIZE, str(cache_size) + "value")
    monkeypatch.setenv(ENV_VAR_DEADLINE_MS, str(deadline) + "value")
    monkeypatch.setenv(ENV_VAR_HOST, host + "value")
    monkeypatch.setenv(ENV_VAR_KEEP_ALIVE_TIME_MS, str(keep_alive) + "value")
    monkeypatch.setenv(ENV_VAR_OFFLINE_FLAG_SOURCE_PATH, offline_path + "value")
    monkeypatch.setenv(ENV_VAR_PORT, str(port) + "value")
    monkeypatch.setenv(ENV_VAR_RETRY_BACKOFF_MS, str(retry_backoff) + "value")
    monkeypatch.setenv(ENV_VAR_STREAM_DEADLINE_MS, str(stream_deadline) + "value")
    monkeypatch.setenv(ENV_VAR_TLS, str(tls) + "value")

    config = Config(
        cache=cache,
        max_cache_size=cache_size,
        deadline_ms=deadline,
        host=host,
        port=port,
        resolver=resolver_type,
        retry_backoff_ms=retry_backoff,
        stream_deadline_ms=stream_deadline,
        tls=tls,
        keep_alive_time=keep_alive,
        offline_flag_source_path=offline_path,
    )
    assert config.cache == cache
    assert config.max_cache_size == cache_size
    assert config.deadline_ms == deadline
    assert config.host == host
    assert config.keep_alive_time == keep_alive
    assert config.offline_flag_source_path == offline_path
    assert config.port == port
    assert config.retry_backoff_ms == retry_backoff
    assert config.stream_deadline_ms == stream_deadline
    assert config.tls is tls
