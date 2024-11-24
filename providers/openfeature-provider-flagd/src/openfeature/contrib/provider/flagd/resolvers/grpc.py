import typing

import grpc
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.schemas.protobuf.flagd.evaluation.v1 import (  # type:ignore[import-not-found]
    evaluation_pb2,
    evaluation_pb2_grpc,
)

from ..config import Config
from ..flag_type import FlagType
from ..protobuf.flagd.evaluation.v1 import evaluation_pb2, evaluation_pb2_grpc

if typing.TYPE_CHECKING:
    from google.protobuf.message import Message

T = typing.TypeVar("T")


class GrpcResolver:
    def __init__(self, config: Config):
        self.config = config
        channel_factory = (
            grpc.secure_channel if self.config.tls else grpc.insecure_channel
        )
        self.channel = channel_factory(f"{self.config.host}:{self.config.port}")
        self.stub = evaluation_pb2_grpc.ServiceStub(self.channel)  # type: ignore[no-untyped-call]

    def shutdown(self) -> None:
        self.channel.close()

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(key, FlagType.BOOLEAN, default_value, evaluation_context)

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve(key, FlagType.STRING, default_value, evaluation_context)

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return self._resolve(key, FlagType.FLOAT, default_value, evaluation_context)

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return self._resolve(key, FlagType.INTEGER, default_value, evaluation_context)

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[dict, list]]:
        return self._resolve(key, FlagType.OBJECT, default_value, evaluation_context)

    def _resolve(  # noqa: PLR0915
        self,
        flag_key: str,
        flag_type: FlagType,
        default_value: T,
        evaluation_context: typing.Optional[EvaluationContext],
    ) -> FlagResolutionDetails[T]:
        context = self._convert_context(evaluation_context)
        call_args = {"timeout": self.config.timeout}
        try:
            request: typing.Union[
                evaluation_pb2.ResolveBooleanRequest,
                evaluation_pb2.ResolveIntRequest,
                evaluation_pb2.ResolveStringRequest,
                evaluation_pb2.ResolveObjectRequest,
                evaluation_pb2.ResolveFloatRequest,
            ]
            if flag_type == FlagType.BOOLEAN:
                request: Message = evaluation_pb2.ResolveBooleanRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveBoolean(request, **call_args)
                value = response.value
            elif flag_type == FlagType.STRING:
                request = evaluation_pb2.ResolveStringRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveString(request, **call_args)
                value = response.value
            elif flag_type == FlagType.OBJECT:
                request = evaluation_pb2.ResolveObjectRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveObject(request, **call_args)
                value = MessageToDict(response, preserving_proto_field_name=True)[
                    "value"
                ]
            elif flag_type == FlagType.FLOAT:
                request = evaluation_pb2.ResolveFloatRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveFloat(request, **call_args)
                value = response.value
            elif flag_type == FlagType.INTEGER:
                request = evaluation_pb2.ResolveIntRequest(
                    flag_key=flag_key, context=context
                )
                response = self.stub.ResolveInt(request, **call_args)
                value = response.value
            else:
                raise ValueError(f"Unknown flag type: {flag_type}")

        except grpc.RpcError as e:
            code = e.code()
            message = f"received grpc status code {code}"

            if code == grpc.StatusCode.NOT_FOUND:
                raise FlagNotFoundError(message) from e
            elif code == grpc.StatusCode.INVALID_ARGUMENT:
                raise TypeMismatchError(message) from e
            elif code == grpc.StatusCode.DATA_LOSS:
                raise ParseError(message) from e
            raise GeneralError(message) from e

        # Got a valid flag and valid type. Return it.
        return FlagResolutionDetails(
            value=value,
            reason=response.reason,
            variant=response.variant,
        )

    def _convert_context(
        self, evaluation_context: typing.Optional[EvaluationContext]
    ) -> Struct:
        s = Struct()
        if evaluation_context:
            try:
                s["targetingKey"] = evaluation_context.targeting_key
                s.update(evaluation_context.attributes)
            except ValueError as exc:
                message = (
                    "could not serialize evaluation context to google.protobuf.Struct"
                )
                raise InvalidContextError(message) from exc
        return s
