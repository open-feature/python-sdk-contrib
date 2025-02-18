import json
import logging
import threading
import time
import typing

import grpc

from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEventDetails
from openfeature.exception import ErrorCode, ParseError, ProviderNotReadyError
from openfeature.schemas.protobuf.flagd.sync.v1 import (
    sync_pb2,
    sync_pb2_grpc,
)

from ....config import Config
from ..connector import FlagStateConnector
from ..flags import FlagStore

logger = logging.getLogger("openfeature.contrib")


class GrpcWatcher(FlagStateConnector):
    def __init__(
        self,
        config: Config,
        flag_store: FlagStore,
        emit_provider_ready: typing.Callable[[ProviderEventDetails], None],
        emit_provider_error: typing.Callable[[ProviderEventDetails], None],
        emit_provider_stale: typing.Callable[[ProviderEventDetails], None],
    ):
        self.flag_store = flag_store
        self.config = config

        self.channel = self._generate_channel(config)
        self.stub = sync_pb2_grpc.FlagSyncServiceStub(self.channel)
        self.retry_backoff_seconds = config.retry_backoff_ms * 0.001
        self.retry_backoff_max_seconds = config.retry_backoff_ms * 0.001
        self.retry_grace_period = config.retry_grace_period
        self.streamline_deadline_seconds = config.stream_deadline_ms * 0.001
        self.deadline = config.deadline_ms * 0.001
        self.selector = config.selector
        self.emit_provider_ready = emit_provider_ready
        self.emit_provider_error = emit_provider_error
        self.emit_provider_stale = emit_provider_stale

        self.connected = False
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
            ("grpc.min_reconnect_backoff_ms", config.stream_deadline_ms),
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

    def initialize(self, context: EvaluationContext) -> None:
        self.connect()

    def connect(self) -> None:
        self.active = True

        # Run monitoring in a separate thread
        self.monitor_thread = threading.Thread(
            target=self.monitor, daemon=True, name="FlagdGrpcSyncServiceMonitorThread"
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

    def _state_change_callback(self, new_state: grpc.ChannelConnectivity) -> None:
        logger.debug(f"gRPC state change: {new_state}")
        if new_state == grpc.ChannelConnectivity.READY:
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(
                    target=self.listen,
                    daemon=True,
                    name="FlagdGrpcSyncWorkerThread",
                )
                self.thread.start()

            if self.timer and self.timer.is_alive():
                logger.debug("gRPC error timer expired")
                self.timer.cancel()

        elif new_state == grpc.ChannelConnectivity.TRANSIENT_FAILURE:
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
        self.emit_provider_error(
            ProviderEventDetails(
                message="gRPC sync disconnected, reconnecting",
                error_code=ErrorCode.GENERAL,
            )
        )

    def shutdown(self) -> None:
        self.active = False
        self.channel.close()

    def listen(self) -> None:
        call_args = (
            {"timeout": self.streamline_deadline_seconds}
            if self.streamline_deadline_seconds > 0
            else {}
        )
        request_args = {"selector": self.selector} if self.selector is not None else {}

        while self.active:
            try:
                request = sync_pb2.SyncFlagsRequest(**request_args)

                logger.debug("Setting up gRPC sync flags connection")
                for flag_rsp in self.stub.SyncFlags(
                    request, wait_for_ready=True, **call_args
                ):
                    flag_str = flag_rsp.flag_configuration
                    logger.debug(
                        f"Received flag configuration - {abs(hash(flag_str)) % (10**8)}"
                    )
                    self.flag_store.update(json.loads(flag_str))

                    if not self.connected:
                        self.emit_provider_ready(
                            ProviderEventDetails(
                                message="gRPC sync connection established"
                            )
                        )
                        self.connected = True

                    if not self.active:
                        logger.debug("Terminating gRPC sync thread")
                        return
            except grpc.RpcError as e:  # noqa: PERF203
                logger.error(f"SyncFlags stream error, {e.code()=} {e.details()=}")
            except json.JSONDecodeError:
                logger.exception(
                    f"Could not parse JSON flag data from SyncFlags endpoint: {flag_str=}"
                )
            except ParseError:
                logger.exception(
                    f"Could not parse flag data using flagd syntax: {flag_str=}"
                )
