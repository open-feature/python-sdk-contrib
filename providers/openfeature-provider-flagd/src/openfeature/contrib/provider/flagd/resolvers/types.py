import typing


class GrpcMultiCallableArgs(typing.TypedDict, total=False):
    timeout: typing.Optional[float]
    wait_for_ready: typing.Optional[bool]
    metadata: typing.Optional[typing.Sequence[typing.Tuple[str, str]]]
