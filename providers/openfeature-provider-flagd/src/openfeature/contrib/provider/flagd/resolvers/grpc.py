import logging
import threading
import time
import typing

import grpc
from cachebox import BaseCacheImpl, LRUCache
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
from grpc import ChannelConnectivity

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
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.schemas.protobuf.flagd.evaluation.v1 import (
    evaluation_pb2,
    evaluation_pb2_grpc,
)

from ..config import CacheType, Config
from ..flag_type import FlagType

if typing.TYPE_CHECKING:
    from google.protobuf.message import Message

T = typing.TypeVar("T")

logger = logging.getLogger("openfeature.contrib")


class GrpcResolver:
    def __init__(
        self,
        config: Config,
        emit_provider_ready: typing.Callable[[ProviderEventDetails], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
        emit_provider_stale: typing.Callable[[ProviderEventDetails], None],
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.active = False
        self.config = config
        self.emit_provider_ready = emit_provider_ready
        self.emit_provider_error = emit_provider_error
        self.emit_provider_stale = emit_provider_stale
        self.emit_provider_configuration_changed = emit_provider_configuration_changed
        self.cache: typing.Optional[BaseCacheImpl] = (
            LRUCache(maxsize=self.config.max_cache_size)
            if self.config.cache == CacheType.LRU
            else None
        )

        self.retry_grace_period = config.retry_grace_period
        self.streamline_deadline_seconds = config.stream_deadline_ms * 0.001
        self.deadline = config.deadline_ms * 0.001
        self.connected = False
        self.channel = self._generate_channel(config)
        self.stub = evaluation_pb2_grpc.ServiceStub(self.channel)

        self.thread: typing.Optional[threading.Thread] = None
        self.timer: typing.Optional[threading.Timer] = None

        self.start_time = time.time()

    def _generate_channel(self, config: Config) -> grpc.Channel:
        target = f"{config.host}:{config.port}"
        # Create the channel with the service config
        options = [
            ("grpc.keepalive_time_ms", config.keep_alive_time),
            ("grpc.initial_reconnect_backoff_ms", config.retry_backoff_ms),
            ("grpc.max_reconnect_backoff_ms", config.retry_backoff_max_ms),
            ("grpc.min_reconnect_backoff_ms", config.deadline_ms),
        ]
        if config.tls:
            channel_args = {
                "options": options,
                "credentials": grpc.ssl_channel_credentials(),
            }
            if config.cert_path:
                with open(config.cert_path, "rb") as f:
                    channel_args["credentials"] = grpc.ssl_channel_credentials(f.read())

            channel = grpc.secure_channel(target, **channel_args)

        else:
            channel = grpc.insecure_channel(
                target,
                options=options,
            )

        return channel

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.connect()

    def shutdown(self) -> None:
        self.active = False
        self.channel.unsubscribe(self._state_change_callback)
        self.channel.close()
        if self.timer and self.timer.is_alive():
            logger.debug("gRPC error timer cancelled due to shutdown")
            self.timer.cancel()
        if self.cache:
            self.cache.clear()

    def connect(self) -> None:
        self.active = True

        # Run monitoring in a separate thread
        self.monitor_thread = threading.Thread(
            target=self.monitor, daemon=True, name="FlagdGrpcServiceMonitorThread"
        )
        self.monitor_thread.start()
        ## block until ready or deadline reached
        timeout = self.deadline + time.time()
        while not self.connected and time.time() < timeout:
            time.sleep(0.05)
        logger.debug("Finished blocking gRPC state initialization")

        if not self.connected:
            raise ProviderNotReadyError(
                "Blocking init finished before data synced. Consider increasing startup deadline to avoid inconsistent evaluations."
            )

    def monitor(self) -> None:
        self.channel.subscribe(self._state_change_callback, try_to_connect=True)

    def _state_change_callback(self, new_state: ChannelConnectivity) -> None:
        logger.debug(f"gRPC state change: {new_state}")
        if new_state == ChannelConnectivity.READY:
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(
                    target=self.listen,
                    daemon=True,
                    name="FlagdGrpcServiceWorkerThread",
                )
                self.thread.start()

            if self.timer and self.timer.is_alive():
                logger.debug("gRPC error timer expired")
                self.timer.cancel()

        elif new_state == ChannelConnectivity.TRANSIENT_FAILURE:
            # this is the failed reconnect attempt so we are going into stale
            self.emit_provider_stale(
                ProviderEventDetails(
                    message="gRPC sync disconnected, reconnecting",
                )
            )
            self.start_time = time.time()
            # adding a timer, so we can emit the error event after time
            self.timer = threading.Timer(self.retry_grace_period, self.emit_error)

            logger.debug("gRPC error timer started")
            self.timer.start()
            self.connected = False

    def emit_error(self) -> None:
        logger.debug("gRPC error emitted")
        if self.cache:
            self.cache.clear()
        self.emit_provider_error(
            ProviderEventDetails(
                message="gRPC sync disconnected, reconnecting",
                error_code=ErrorCode.GENERAL,
            )
        )

    def listen(self) -> None:
        logger.debug("gRPC starting listener thread")
        call_args = (
            {"timeout": self.streamline_deadline_seconds}
            if self.streamline_deadline_seconds > 0
            else {}
        )
        request = evaluation_pb2.EventStreamRequest()

        # defining a never ending loop to recreate the stream
        while self.active:
            try:
                logger.debug("Setting up gRPC sync flags connection")
                for message in self.stub.EventStream(
                    request, wait_for_ready=True, **call_args
                ):
                    if message.type == "provider_ready":
                        self.emit_provider_ready(
                            ProviderEventDetails(
                                message="gRPC sync connection established"
                            )
                        )
                        self.connected = True
                    elif message.type == "configuration_change":
                        data = MessageToDict(message)["data"]
                        self.handle_changed_flags(data)

                    if not self.active:
                        logger.info("Terminating gRPC sync thread")
                        return
            except grpc.RpcError as e:  # noqa: PERF203
                # although it seems like this error log is not interesting, without it, the retry is not working as expected
                logger.debug(f"SyncFlags stream error, {e.code()=} {e.details()=}")
            except ParseError:
                logger.exception(
                    f"Could not parse flag data using flagd syntax: {message=}"
                )

    def handle_changed_flags(self, data: typing.Any) -> None:
        changed_flags = list(data["flags"].keys())

        if self.cache:
            for flag in changed_flags:
                self.cache.pop(flag)

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

    def _resolve(  # noqa: PLR0915 C901
        self,
        flag_key: str,
        flag_type: FlagType,
        default_value: T,
        evaluation_context: typing.Optional[EvaluationContext],
    ) -> FlagResolutionDetails[T]:
        if self.cache is not None and flag_key in self.cache:
            cached_flag: FlagResolutionDetails[T] = self.cache[flag_key]
            cached_flag.reason = Reason.CACHED
            return cached_flag

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
        result = FlagResolutionDetails(
            value=value,
            reason=response.reason,
            variant=response.variant,
        )

        if response.reason == Reason.STATIC and self.cache is not None:
            self.cache.insert(flag_key, result)

        return result

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
