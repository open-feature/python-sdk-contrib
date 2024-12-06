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
    ):
        self.flag_store = flag_store
        self.config = config

        self.stub, self.channel = self.create_stub()
        self.retry_backoff_seconds = config.retry_backoff_ms * 0.001
        self.retry_backoff_max_seconds = config.retry_backoff_ms * 0.001
        self.retry_grace_attempts = config.retry_grace_attempts
        self.streamline_deadline_seconds = config.stream_deadline_ms * 0.001
        self.deadline = config.deadline_ms * 0.001
        self.selector = config.selector
        self.emit_provider_ready = emit_provider_ready
        self.emit_provider_error = emit_provider_error

        self.connected = False

    def create_stub(
        self,
    ) -> typing.Tuple[sync_pb2_grpc.FlagSyncServiceStub, grpc.Channel]:
        config = self.config
        channel_factory = grpc.secure_channel if config.tls else grpc.insecure_channel
        channel = channel_factory(
            f"{config.host}:{config.port}",
            options=(("grpc.keepalive_time_ms", config.keep_alive_time),),
        )
        stub = sync_pb2_grpc.FlagSyncServiceStub(channel)
        return stub, channel

    def initialize(self, context: EvaluationContext) -> None:
        self.active = True
        self.thread = threading.Thread(
            target=self.sync_flags, daemon=True, name="FlagdGrpcSyncWorkerThread"
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

    def shutdown(self) -> None:
        self.active = False
        self.channel.close()

    def sync_flags(self) -> None:
        retry_delay = self.retry_backoff_seconds
        call_args = (
            {"timeout": self.streamline_deadline_seconds}
            if self.streamline_deadline_seconds > 0
            else {}
        )

        while self.active:
            try:
                request_args = (
                    {"selector": self.selector} if self.selector is not None else {}
                )
                request = sync_pb2.SyncFlagsRequest(**request_args)

                logger.debug("Setting up gRPC sync flags connection")
                for flag_rsp in self.stub.SyncFlags(request, **call_args):
                    flag_str = flag_rsp.flag_configuration
                    logger.debug(
                        f"Received flag configuration - {abs(hash(flag_str)) % (10 ** 8)}"
                    )
                    self.flag_store.update(json.loads(flag_str))

                    if not self.connected:
                        self.emit_provider_ready(
                            ProviderEventDetails(
                                message="gRPC sync connection established"
                            )
                        )
                        self.connected = True
                        # reset retry delay after successsful read
                        retry_delay = self.retry_backoff_seconds
                    if not self.active:
                        logger.info("Terminating gRPC sync thread")
                        return
            except grpc.RpcError as e:
                logger.error(f"SyncFlags stream error, {e.code()=} {e.details()=}")
                # re-create the stub if there's a connection issue - otherwise reconnect does not work as expected
                self.stub, self.channel = self.create_stub()
            except json.JSONDecodeError:
                logger.exception(
                    f"Could not parse JSON flag data from SyncFlags endpoint: {flag_str=}"
                )
            except ParseError:
                logger.exception(
                    f"Could not parse flag data using flagd syntax: {flag_str=}"
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
            retry_delay = min(1.1 * retry_delay, self.retry_backoff_max_seconds)
