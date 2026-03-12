import logging
import os
import time
import typing
from pathlib import Path

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc
from testcontainers.compose import DockerCompose

from openfeature.contrib.provider.flagd.config import ResolverType

logger = logging.getLogger(__name__)

HEALTH_CHECK = 8014
LAUNCHPAD = 8080
FORBIDDEN = 9212


class FlagdContainer:
    """Manages the docker-compose environment for flagd e2e tests.

    Uses docker-compose to start both flagd and envoy containers,
    so the envoy forbidden endpoint (port 9212) returns a proper HTTP 403.
    """

    def __init__(
        self,
        feature: typing.Optional[str] = None,
        **kwargs,
    ) -> None:
        self._test_harness_dir = (
            Path(__file__).parents[2] / "openfeature" / "test-harness"
        )
        self._version = (self._test_harness_dir / "version.txt").read_text().rstrip()

        image: str = "ghcr.io/open-feature/flagd-testbed"
        if feature is not None:
            image = f"{image}-{feature}"

        self.flagDir = Path("./flags")
        self.flagDir.mkdir(parents=True, exist_ok=True)

        # Set environment variables for docker-compose substitution
        os.environ["IMAGE"] = image
        os.environ["VERSION"] = f"v{self._version}"
        os.environ["FLAGS_DIR"] = str(self.flagDir.absolute())

        self._compose = DockerCompose(
            context=str(self._test_harness_dir),
            compose_file_name="docker-compose.yaml",
            wait=True,
        )

    def get_port(self, resolver_type: ResolverType) -> int:
        if resolver_type == ResolverType.RPC:
            return self._compose.get_service_port("flagd", 8013)
        else:
            return self._compose.get_service_port("flagd", 8015)

    def get_exposed_port(self, port: int) -> int:
        """Get mapped port. For FORBIDDEN (9212) returns envoy port, otherwise flagd port."""
        if port == FORBIDDEN:
            return self._compose.get_service_port("envoy", FORBIDDEN)
        return self._compose.get_service_port("flagd", port)

    def get_launchpad_url(self) -> str:
        port = self._compose.get_service_port("flagd", LAUNCHPAD)
        return f"http://localhost:{port}"

    def start(self) -> "FlagdContainer":
        self._compose.start()
        host = self._compose.get_service_host("flagd", HEALTH_CHECK) or "localhost"
        port = self._compose.get_service_port("flagd", HEALTH_CHECK)
        self._checker(host, port)
        return self

    def stop(self) -> None:
        self._compose.stop()

    def _checker(self, host: str, port: int) -> None:
        # Give an extra second before continuing
        time.sleep(1)
        # Use the GRPC health check endpoint
        with grpc.insecure_channel(f"{host}:{port}") as channel:
            health_stub = health_pb2_grpc.HealthStub(channel)

            def health_check_call(stub: health_pb2_grpc.HealthStub):
                request = health_pb2.HealthCheckRequest()
                try:
                    resp = stub.Check(request)
                    return resp.status == health_pb2.HealthCheckResponse.SERVING
                except Exception:
                    return False

            # Check health status every 1 second for 30 seconds
            ok = False
            for _ in range(30):
                ok = health_check_call(health_stub)
                if ok:
                    break
                time.sleep(1)

            if not ok:
                raise ConnectionError("flagd not ready in time")
