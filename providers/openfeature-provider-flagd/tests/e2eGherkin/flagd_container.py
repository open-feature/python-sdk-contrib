import time
from time import sleep

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_is_ready, wait_for_logs

HEALTH_CHECK = 8014


class FlagDContainer(DockerContainer):
    def __init__(
        self,
        image: str = "ghcr.io/open-feature/flagd-testbed:v0.5.10",
        port: int = 8013,
        **kwargs,
    ) -> None:
        super().__init__(image, **kwargs)
        self.port = port
        self.with_exposed_ports(self.port, HEALTH_CHECK)

    def start(self) -> "FlagDContainer":
        super().start()
        self._checker(self.get_container_host_ip(), self.get_exposed_port(HEALTH_CHECK))
        return self

    @wait_container_is_ready(ConnectionError)
    def _checker(self, host: str, port: int) -> None:
        # First we wait for Flagd to say it's listening
        wait_for_logs(
            self,
            "Flag IResolver listening at",
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
                sleep(1)

            if not ok:
                raise ConnectionError("flagD not ready in time")
