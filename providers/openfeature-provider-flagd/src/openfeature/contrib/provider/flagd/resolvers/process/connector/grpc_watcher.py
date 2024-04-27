import json
import logging
import threading
import time
import typing

import grpc

from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError
from openfeature.provider.provider import AbstractProvider

from ....config import Config
from ....proto.flagd.sync.v1 import sync_pb2, sync_pb2_grpc
from ..flags import Flag, FlagStore

logger = logging.getLogger("openfeature.contrib")


class GrpcWatcherFlagStore(FlagStore):
    INIT_BACK_OFF = 2
    MAX_BACK_OFF = 120

    def __init__(self, config: Config, provider: AbstractProvider):
        self.provider = provider
        self.flag_data: typing.Mapping[str, Flag] = {}
        channel_factory = grpc.secure_channel if config.tls else grpc.insecure_channel
        self.channel = channel_factory(f"{config.host}:{config.port}")
        self.stub = sync_pb2_grpc.FlagSyncServiceStub(self.channel)

        self.connected = False

        # TODO: Add selector

        self.thread = threading.Thread(target=self.sync_flags, daemon=True)
        self.thread.start()

        ## block until ready or deadline reached

        # TODO: get deadline from user
        deadline = 2 + time.time()
        while not self.connected and time.time() < deadline:
            logger.debug("blocking on init")
            time.sleep(0.05)

        if not self.connected:
            logger.warning(
                "Blocking init finished before data synced. Consider increasing startup deadline to avoid inconsistent evaluations."
            )

    def shutdown(self) -> None:
        pass

    def get_flag(self, key: str) -> typing.Optional[Flag]:
        return self.flag_data.get(key)

    def sync_flags(self) -> None:
        request = sync_pb2.SyncFlagsRequest()  # type:ignore[attr-defined]

        retry_delay = self.INIT_BACK_OFF
        while True:
            try:
                logger.debug("Setting up gRPC sync flags connection")
                for flag_rsp in self.stub.SyncFlags(request):
                    flag_str = flag_rsp.flag_configuration
                    logger.debug(
                        f"Received flag configuration - {abs(hash(flag_str)) % (10 ** 8)}"
                    )
                    self.flag_data = Flag.parse_flags(json.loads(flag_str))

                    self.connected = True
                    self.provider.emit_provider_configuration_changed(
                        ProviderEventDetails(flags_changed=list(self.flag_data.keys()))
                    )

                    # reset retry delay after successsful read
                    retry_delay = self.INIT_BACK_OFF
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
            finally:
                # self.connected = False
                logger.info(f"Reconnecting in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay = min(2 * retry_delay, self.MAX_BACK_OFF)
