import dataclasses
import os
import typing
from enum import Enum


class ResolverType(Enum):
    RPC = "rpc"
    IN_PROCESS = "in-process"
    FILE = "file"


class CacheType(Enum):
    LRU = "lru"
    DISABLED = "disabled"


DEFAULT_CACHE = CacheType.LRU
DEFAULT_CACHE_SIZE = 1000
DEFAULT_DEADLINE = 500
DEFAULT_HOST = "localhost"
DEFAULT_KEEP_ALIVE = 0
DEFAULT_OFFLINE_SOURCE_PATH: typing.Optional[str] = None
DEFAULT_OFFLINE_POLL_MS = 5000
DEFAULT_PORT_IN_PROCESS = 8015
DEFAULT_PORT_RPC = 8013
DEFAULT_RESOLVER_TYPE = ResolverType.RPC
DEFAULT_RETRY_BACKOFF = 1000
DEFAULT_RETRY_BACKOFF_MAX = 120000
DEFAULT_RETRY_GRACE_PERIOD_SECONDS = 5
DEFAULT_STREAM_DEADLINE = 600000
DEFAULT_TLS = False
DEFAULT_TLS_CERT: typing.Optional[str] = None

ENV_VAR_CACHE_SIZE = "FLAGD_MAX_CACHE_SIZE"
ENV_VAR_CACHE_TYPE = "FLAGD_CACHE"
ENV_VAR_DEADLINE_MS = "FLAGD_DEADLINE_MS"
ENV_VAR_HOST = "FLAGD_HOST"
ENV_VAR_KEEP_ALIVE_TIME_MS = "FLAGD_KEEP_ALIVE_TIME_MS"
ENV_VAR_OFFLINE_FLAG_SOURCE_PATH = "FLAGD_OFFLINE_FLAG_SOURCE_PATH"
ENV_VAR_OFFLINE_POLL_MS = "FLAGD_OFFLINE_POLL_MS"
ENV_VAR_PORT = "FLAGD_PORT"
ENV_VAR_RESOLVER_TYPE = "FLAGD_RESOLVER"
ENV_VAR_RETRY_BACKOFF_MS = "FLAGD_RETRY_BACKOFF_MS"
ENV_VAR_RETRY_BACKOFF_MAX_MS = "FLAGD_RETRY_BACKOFF_MAX_MS"
ENV_VAR_RETRY_GRACE_PERIOD_SECONDS = "FLAGD_RETRY_GRACE_PERIOD"
ENV_VAR_SELECTOR = "FLAGD_SOURCE_SELECTOR"
ENV_VAR_STREAM_DEADLINE_MS = "FLAGD_STREAM_DEADLINE_MS"
ENV_VAR_TLS = "FLAGD_TLS"
ENV_VAR_TLS_CERT = "FLAGD_SERVER_CERT_PATH"

T = typing.TypeVar("T")


def str_to_bool(val: str) -> bool:
    return val.lower() == "true"


def convert_resolver_type(val: typing.Union[str, ResolverType]) -> ResolverType:
    if isinstance(val, str):
        v = val.lower()
        return ResolverType(v)
    else:
        return ResolverType(val)


def env_or_default(
    env_var: str, default: T, cast: typing.Optional[typing.Callable[[str], T]] = None
) -> typing.Union[str, T]:
    val = os.environ.get(env_var)
    if val is None:
        return default
    return val if cast is None else cast(val)


@dataclasses.dataclass
class Config:
    def __init__(  # noqa: PLR0913
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        selector: typing.Optional[str] = None,
        resolver: typing.Optional[ResolverType] = None,
        offline_flag_source_path: typing.Optional[str] = None,
        offline_poll_interval_ms: typing.Optional[int] = None,
        retry_backoff_ms: typing.Optional[int] = None,
        retry_backoff_max_ms: typing.Optional[int] = None,
        retry_grace_period: typing.Optional[int] = None,
        deadline_ms: typing.Optional[int] = None,
        stream_deadline_ms: typing.Optional[int] = None,
        keep_alive_time: typing.Optional[int] = None,
        cache: typing.Optional[CacheType] = None,
        max_cache_size: typing.Optional[int] = None,
        cert_path: typing.Optional[str] = None,
    ):
        self.host = env_or_default(ENV_VAR_HOST, DEFAULT_HOST) if host is None else host

        self.tls = (
            env_or_default(ENV_VAR_TLS, DEFAULT_TLS, cast=str_to_bool)
            if tls is None
            else tls
        )

        self.retry_backoff_ms: int = (
            int(
                env_or_default(
                    ENV_VAR_RETRY_BACKOFF_MS, DEFAULT_RETRY_BACKOFF, cast=int
                )
            )
            if retry_backoff_ms is None
            else retry_backoff_ms
        )
        self.retry_backoff_max_ms: int = (
            int(
                env_or_default(
                    ENV_VAR_RETRY_BACKOFF_MAX_MS, DEFAULT_RETRY_BACKOFF_MAX, cast=int
                )
            )
            if retry_backoff_max_ms is None
            else retry_backoff_max_ms
        )

        self.retry_grace_period: int = (
            int(
                env_or_default(
                    ENV_VAR_RETRY_GRACE_PERIOD_SECONDS,
                    DEFAULT_RETRY_GRACE_PERIOD_SECONDS,
                    cast=int,
                )
            )
            if retry_grace_period is None
            else retry_grace_period
        )

        self.resolver = (
            env_or_default(
                ENV_VAR_RESOLVER_TYPE, DEFAULT_RESOLVER_TYPE, cast=convert_resolver_type
            )
            if resolver is None
            else resolver
        )

        default_port = (
            DEFAULT_PORT_RPC
            if self.resolver is ResolverType.RPC
            else DEFAULT_PORT_IN_PROCESS
        )

        self.port: int = (
            int(env_or_default(ENV_VAR_PORT, default_port, cast=int))
            if port is None
            else port
        )

        self.offline_flag_source_path = (
            env_or_default(
                ENV_VAR_OFFLINE_FLAG_SOURCE_PATH, DEFAULT_OFFLINE_SOURCE_PATH
            )
            if offline_flag_source_path is None
            else offline_flag_source_path
        )

        if (
            self.offline_flag_source_path is not None
            and self.resolver is ResolverType.IN_PROCESS
        ):
            self.resolver = ResolverType.FILE

        if self.resolver is ResolverType.FILE and self.offline_flag_source_path is None:
            raise AttributeError(
                "Resolver Type 'FILE' requires a offlineFlagSourcePath"
            )

        self.offline_poll_interval_ms: int = (
            int(
                env_or_default(
                    ENV_VAR_OFFLINE_POLL_MS, DEFAULT_OFFLINE_POLL_MS, cast=int
                )
            )
            if offline_poll_interval_ms is None
            else offline_poll_interval_ms
        )

        self.deadline_ms: int = (
            int(env_or_default(ENV_VAR_DEADLINE_MS, DEFAULT_DEADLINE, cast=int))
            if deadline_ms is None
            else deadline_ms
        )

        self.stream_deadline_ms: int = (
            int(
                env_or_default(
                    ENV_VAR_STREAM_DEADLINE_MS, DEFAULT_STREAM_DEADLINE, cast=int
                )
            )
            if stream_deadline_ms is None
            else stream_deadline_ms
        )

        self.keep_alive_time: int = (
            int(
                env_or_default(ENV_VAR_KEEP_ALIVE_TIME_MS, DEFAULT_KEEP_ALIVE, cast=int)
            )
            if keep_alive_time is None
            else keep_alive_time
        )

        self.cache = (
            CacheType(env_or_default(ENV_VAR_CACHE_TYPE, DEFAULT_CACHE))
            if cache is None
            else cache
        )

        self.max_cache_size: int = (
            int(env_or_default(ENV_VAR_CACHE_SIZE, DEFAULT_CACHE_SIZE, cast=int))
            if max_cache_size is None
            else max_cache_size
        )

        self.cert_path = (
            env_or_default(ENV_VAR_TLS_CERT, DEFAULT_TLS_CERT)
            if cert_path is None
            else cert_path
        )

        self.selector = (
            env_or_default(ENV_VAR_SELECTOR, None) if selector is None else selector
        )
