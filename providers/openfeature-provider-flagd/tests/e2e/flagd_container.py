import os.path
import time
import typing
from pathlib import Path

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready, wait_for_logs

from openfeature.contrib.provider.flagd.config import ResolverType

HEALTH_CHECK = 8014
LAUNCHPAD = 8080


class FlagdContainer(DockerContainer):
    def __init__(
        self,
        feature: typing.Optional[str] = None,
        **kwargs,
    ) -> None:
        image: str = "ghcr.io/open-feature/flagd-testbed"
        if feature is not None:
            image = f"{image}-{feature}"
        path = Path(__file__).parents[2] / "openfeature/test-harness/version.txt"
        data = path.read_text().rstrip()
        super().__init__(f"{image}:v{data}", **kwargs)
        self.rpc = 8013
        self.ipr = 8015
        self.flagDir = Path("./flags")
        self.flagDir.mkdir(parents=True, exist_ok=True)
        self.with_exposed_ports(self.rpc, self.ipr, HEALTH_CHECK, LAUNCHPAD)
        self.with_volume_mapping(os.path.abspath(self.flagDir.name), "/flags", "rw")

    def get_port(self, resolver_type: ResolverType):
        if resolver_type == ResolverType.RPC:
            return self.get_exposed_port(self.rpc)
        else:
            return self.get_exposed_port(self.ipr)

    def get_launchpad_url(self):
        return f"http://localhost:{self.get_exposed_port(LAUNCHPAD)}"

    def start(self) -> "FlagdContainer":
        super().start()
        self._checker(self.get_container_host_ip(), self.get_exposed_port(HEALTH_CHECK))
        return self

    @wait_container_is_ready(ConnectionError)
    def _checker(self, host: str, port: str) -> None:
        # First we wait for Flagd to say it's listening
        wait_for_logs(
            self,
            "listening",
            5,
        )

        time.sleep(1)
        # Second we use the GRPC health check endpoint
        with grpc.insecure_channel(host + ":" + port) as channel:
            health_stub = health_pb2_grpc.HealthStub(channel)

            def health_check_call(stub: health_pb2_grpc.HealthStub):
                request = health_pb2.HealthCheckRequest()
                resp = stub.Check(request)
                if resp.status == health_pb2.HealthCheckResponse.SERVING:
                    return True
                elif resp.status == health_pb2.HealthCheckResponse.NOT_SERVING:
                    return False

            # Should succeed
            # Check health status every 1 second for 30 seconds
            ok = False
            for _ in range(30):
                ok = health_check_call(health_stub)
                if ok:
                    break
                time.sleep(1)

            if not ok:
                raise ConnectionError("flagD not ready in time")
