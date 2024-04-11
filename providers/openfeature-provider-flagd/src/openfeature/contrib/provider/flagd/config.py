import os
import typing
from enum import Enum

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


class ResolverType(Enum):
    GRPC = "grpc"
    IN_PROCESS = "in-process"


class Config:
    def __init__(  # noqa: PLR0913
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        timeout: typing.Optional[int] = None,
        resolver_type: typing.Optional[ResolverType] = None,
        offline_flag_source_path: typing.Optional[str] = None,
        offline_poll_interval_seconds: typing.Optional[float] = None,
    ):
        self.host = env_or_default("FLAGD_HOST", "localhost") if host is None else host
        self.port = (
            env_or_default("FLAGD_PORT", 8013, cast=int) if port is None else port
        )
        self.tls = (
            env_or_default("FLAGD_TLS", False, cast=str_to_bool) if tls is None else tls
        )
        self.timeout = 5 if timeout is None else timeout
        self.resolver_type = (
            ResolverType(env_or_default("FLAGD_RESOLVER_TYPE", "grpc"))
            if resolver_type is None
            else resolver_type
        )
        self.offline_flag_source_path = (
            env_or_default("FLAGD_OFFLINE_FLAG_SOURCE_PATH", None)
            if offline_flag_source_path is None
            else offline_flag_source_path
        )
        self.offline_poll_interval_seconds = (
            float(env_or_default("FLAGD_OFFLINE_POLL_INTERVAL_SECONDS", 1.0))
            if offline_poll_interval_seconds is None
            else offline_poll_interval_seconds
        )
