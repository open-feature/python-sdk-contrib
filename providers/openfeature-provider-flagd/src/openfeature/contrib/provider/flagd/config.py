import os
import typing
from enum import Enum


class ResolverType(Enum):
    RPC = "rpc"
    IN_PROCESS = "in-process"


DEFAULT_DEADLINE = 500
DEFAULT_HOST = "localhost"
DEFAULT_KEEP_ALIVE = 0
DEFAULT_OFFLINE_SOURCE_PATH: typing.Optional[str] = None
DEFAULT_PORT_IN_PROCESS = 8015
DEFAULT_PORT_RPC = 8013
DEFAULT_RESOLVER_TYPE = ResolverType.RPC
DEFAULT_RETRY_BACKOFF = 1000
DEFAULT_STREAM_DEADLINE = 600000
DEFAULT_TLS = False

ENV_VAR_DEADLINE_MS = "FLAGD_DEADLINE_MS"
ENV_VAR_HOST = "FLAGD_HOST"
ENV_VAR_KEEP_ALIVE_TIME_MS = "FLAGD_KEEP_ALIVE_TIME_MS"
ENV_VAR_OFFLINE_FLAG_SOURCE_PATH = "FLAGD_OFFLINE_FLAG_SOURCE_PATH"
ENV_VAR_PORT = "FLAGD_PORT"
ENV_VAR_RESOLVER_TYPE = "FLAGD_RESOLVER_TYPE"
ENV_VAR_RETRY_BACKOFF_MS = "FLAGD_RETRY_BACKOFF_MS"
ENV_VAR_STREAM_DEADLINE_MS = "FLAGD_STREAM_DEADLINE_MS"
ENV_VAR_TLS = "FLAGD_TLS"

T = typing.TypeVar("T")


def str_to_bool(val: str) -> bool:
    return val.lower() == "true"


def env_or_default(
    env_var: str, default: T, cast: typing.Optional[typing.Callable[[str], T]] = None
) -> typing.Union[str, T]:
    val = os.environ.get(env_var)
    if val is None:
        return default
    return val if cast is None else cast(val)


class Config:
    def __init__(  # noqa: PLR0913
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        resolver_type: typing.Optional[ResolverType] = None,
        offline_flag_source_path: typing.Optional[str] = None,
        retry_backoff_ms: typing.Optional[int] = None,
        deadline: typing.Optional[int] = None,
        stream_deadline_ms: typing.Optional[int] = None,
        keep_alive_time: typing.Optional[int] = None,
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

        self.resolver_type = (
            ResolverType(env_or_default(ENV_VAR_RESOLVER_TYPE, DEFAULT_RESOLVER_TYPE))
            if resolver_type is None
            else resolver_type
        )

        default_port = (
            DEFAULT_PORT_RPC
            if self.resolver_type is ResolverType.RPC
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

        self.deadline: int = (
            int(env_or_default(ENV_VAR_DEADLINE_MS, DEFAULT_DEADLINE, cast=int))
            if deadline is None
            else deadline
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
