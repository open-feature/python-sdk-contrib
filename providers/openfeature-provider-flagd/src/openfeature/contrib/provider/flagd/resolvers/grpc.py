import logging
import threading
import time
import typing

import grpc
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct

from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import (
    ErrorCode,
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
    ProviderNotReadyError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.schemas.protobuf.flagd.evaluation.v1 import (
    evaluation_pb2,
    evaluation_pb2_grpc,
)

from ..config import Config
from ..flag_type import FlagType

if typing.TYPE_CHECKING:
    from google.protobuf.message import Message

T = typing.TypeVar("T")

logger = logging.getLogger("openfeature.contrib")


class GrpcResolver:
    MAX_BACK_OFF = 120

    def __init__(
        self,
        config: Config,
        emit_provider_ready: typing.Callable[[ProviderEventDetails], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.config = config
        self.emit_provider_ready = emit_provider_ready
        self.emit_provider_error = emit_provider_error
        self.emit_provider_configuration_changed = emit_provider_configuration_changed
        self.stub, self.channel = self._create_stub()
        self.retry_backoff_seconds = config.retry_backoff_ms * 0.001
        self.streamline_deadline_seconds = config.stream_deadline_ms * 0.001
        self.deadline = config.deadline * 0.001
        self.connected = False

    def _create_stub(
        self,
    ) -> typing.Tuple[evaluation_pb2_grpc.ServiceStub, grpc.Channel]:
        config = self.config
        channel_factory = grpc.secure_channel if config.tls else grpc.insecure_channel
        channel = channel_factory(
            f"{config.host}:{config.port}",
            options=(("grpc.keepalive_time_ms", config.keep_alive_time),),
        )
        stub = evaluation_pb2_grpc.ServiceStub(channel)
        return stub, channel

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.connect()

    def shutdown(self) -> None:
        self.active = False
        self.channel.close()

    def connect(self) -> None:
        self.active = True
        self.thread = threading.Thread(
            target=self.listen, daemon=True, name="FlagdGrpcServiceWorkerThread"
        )
        self.thread.start()

        ## block until ready or deadline reached
        timeout = self.deadline + time.time()
        while not self.connected and time.time() < timeout:
            time.sleep(0.05)
        logger.debug("Finished blocking gRPC state initialization")

        if not self.connected:
            raise ProviderNotReadyError(
                "Blocking init finished before data synced. Consider increasing startup deadline to avoid inconsistent evaluations."
            )

    def listen(self) -> None:
        retry_delay = self.retry_backoff_seconds

        call_args = (
            {"timeout": self.streamline_deadline_seconds}
            if self.streamline_deadline_seconds > 0
            else {}
        )
        while self.active:
            request = evaluation_pb2.EventStreamRequest()
            try:
                logger.debug("Setting up gRPC sync flags connection")
                for message in self.stub.EventStream(request, **call_args):
                    if message.type == "provider_ready":
                        if not self.connected:
                            self.emit_provider_ready(
                                ProviderEventDetails(
                                    message="gRPC sync connection established"
                                )
                            )
                            self.connected = True
                            # reset retry delay after successsful read
                            retry_delay = self.retry_backoff_seconds

                    elif message.type == "configuration_change":
                        data = MessageToDict(message)["data"]
                        self.handle_changed_flags(data)

                    if not self.active:
                        logger.info("Terminating gRPC sync thread")
                        return
            except grpc.RpcError as e:
                logger.error(f"SyncFlags stream error, {e.code()=} {e.details()=}")
                # re-create the stub if there's a connection issue - otherwise reconnect does not work as expected
                self.stub, self.channel = self._create_stub()
            except ParseError:
                logger.exception(
                    f"Could not parse flag data using flagd syntax: {message=}"
                )

            self.connected = False
            self.emit_provider_error(
                ProviderEventDetails(
                    message=f"gRPC sync disconnected, reconnecting in {retry_delay}s",
                    error_code=ErrorCode.GENERAL,
                )
            )
            logger.info(f"gRPC sync disconnected, reconnecting in {retry_delay}s")
            time.sleep(retry_delay)
            retry_delay = min(1.1 * retry_delay, self.MAX_BACK_OFF)

    def handle_changed_flags(self, data: typing.Any) -> None:
        changed_flags = list(data["flags"].keys())

        self.emit_provider_configuration_changed(ProviderEventDetails(changed_flags))

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
        call_args = {"timeout": self.deadline}
        try:
            request: Message
            if flag_type == FlagType.BOOLEAN:
                request = evaluation_pb2.ResolveBooleanRequest(
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
