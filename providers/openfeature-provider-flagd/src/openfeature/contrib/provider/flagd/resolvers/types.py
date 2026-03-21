import typing


class GrpcMultiCallableArgs(typing.TypedDict, total=False):
    timeout: float | None
    wait_for_ready: bool | None
    metadata: tuple[tuple[str, str]] | None
