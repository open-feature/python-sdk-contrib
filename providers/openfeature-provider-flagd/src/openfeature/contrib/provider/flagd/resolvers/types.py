import typing


class GrpcMultiCallableArgs(typing.TypedDict, total=False):
    timeout: typing.Optional[float]
    wait_for_ready: typing.Optional[bool]
    metadata: typing.Optional[typing.Tuple[typing.Tuple[str, str]]]
