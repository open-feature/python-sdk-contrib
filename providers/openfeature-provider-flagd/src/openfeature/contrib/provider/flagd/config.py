import os
import typing

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
    def __init__(
        self,
        host: typing.Optional[str] = None,
        port: typing.Optional[int] = None,
        tls: typing.Optional[bool] = None,
        timeout: typing.Optional[int] = None,
    ):
        self.host = env_or_default("FLAGD_HOST", "localhost") if host is None else host
        self.port = (
            env_or_default("FLAGD_PORT", 8013, cast=int) if port is None else port
        )
        self.tls = (
            env_or_default("FLAGD_TLS", False, cast=str_to_bool) if tls is None else tls
        )
        self.timeout = 5 if timeout is None else timeout
