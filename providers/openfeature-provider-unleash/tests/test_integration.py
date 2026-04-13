"""Integration tests for Unleash provider using testcontainers."""

import logging
import time
from datetime import datetime, timezone

import psycopg2
import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext

# Configuration for the running Unleash instance (will be set by fixtures)
UNLEASH_URL = None
API_TOKEN = "default:development.unleash-insecure-api-token"  # noqa: S105
ADMIN_TOKEN = "user:76672ac99726f8e48a1bbba16b7094a50d1eee3583d1e8457e12187a"  # noqa: S105

logger = logging.getLogger("openfeature.contrib.tests")


class UnleashContainer(DockerContainer):
    """Custom Unleash container with health check."""

    def __init__(self, postgres_url: str, **kwargs):
        super().__init__("unleashorg/unleash-server:latest", **kwargs)
        self.postgres_url = postgres_url

    def _configure(self):
        self.with_env("DATABASE_URL", self.postgres_url)
        self.with_env("DATABASE_URL_FILE", "")
        self.with_env("DATABASE_SSL", "false")
        self.with_env("DATABASE_SSL_REJECT_UNAUTHORIZED", "false")
        self.with_env("LOG_LEVEL", "info")
        self.with_env("PORT", "4242")
        self.with_env("HOST", "0.0.0.0")  # noqa: S104
        self.with_env("ADMIN_AUTHENTICATION", "none")
        self.with_env("AUTH_ENABLE", "false")
        self.with_env("INIT_CLIENT_API_TOKENS", API_TOKEN)
        # Expose the Unleash port
        self.with_exposed_ports(4242)


def insert_admin_token(postgres_container):
    """Insert admin token into the Unleash database."""
    url = postgres_container.get_connection_url()
    conn = psycopg2.connect(url)

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                    INSERT INTO "public"."personal_access_tokens"
                    ("secret", "description", "user_id", "expires_at", "seen_at", "created_at", "id")
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """,
                (
                    "user:76672ac99726f8e48a1bbba16b7094a50d1eee3583d1e8457e12187a",
                    "my-token",
                    1,
                    datetime(3025, 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    1,
                ),
            )
            conn.commit()
            logger.info("Admin token inserted successfully")
    except Exception as e:
        logger.error(f"Error inserting admin token: {e}")
        conn.rollback()
    finally:
        conn.close()


def create_test_flags():
    """Create test flags in the Unleash instance."""
    flags = [
        {
            "name": "integration-boolean-flag",
            "description": "Boolean feature flag for testing",
            "type": "release",
            "enabled": True,
        },
        {
            "name": "integration-string-flag",
            "description": "String feature flag for testing",
            "type": "release",
            "enabled": True,
        },
        {
            "name": "integration-float-flag",
            "description": "Float feature flag for testing",
            "type": "release",
            "enabled": True,
        },
        {
            "name": "integration-object-flag",
            "description": "Object feature flag for testing",
            "type": "release",
            "enabled": True,
        },
        {
            "name": "integration-integer-flag",
            "description": "Integer feature flag for testing",
            "type": "release",
            "enabled": True,
        },
        {
            "name": "integration-targeting-flag",
            "description": "Targeting feature flag for testing",
            "type": "release",
            "enabled": True,
        },
    ]

    headers = {"Authorization": ADMIN_TOKEN, "Content-Type": "application/json"}

    for flag in flags:
        try:
            response = requests.post(
                f"{UNLEASH_URL}/api/admin/projects/default/features",
                headers=headers,
                json=flag,
                timeout=10,
            )
            if response.status_code in [200, 201, 409]:
                logger.info(f"Flag '{flag['name']}' created")
                add_strategy_with_variants(flag["name"], headers)
                enable_flag(flag["name"], headers)
            else:
                logger.error(
                    f"Failed to create flag '{flag['name']}': {response.status_code}"
                )
        except Exception as e:  # noqa: PERF203
            logger.error(f"Error creating flag '{flag['name']}': {e}")


def add_strategy_with_variants(flag_name: str, headers: dict):
    """Add strategy with variants to a flag."""
    variant_configs = {
        "integration-boolean-flag": [
            {
                "stickiness": "default",
                "name": "true",
                "weight": 1000,
                "payload": {"type": "string", "value": "true"},
                "weightType": "variable",
            }
        ],
        "integration-string-flag": [
            {
                "stickiness": "default",
                "name": "my-string",
                "weight": 1000,
                "payload": {"type": "string", "value": "my-string"},
                "weightType": "variable",
            }
        ],
        "integration-float-flag": [
            {
                "stickiness": "default",
                "name": "9000.5",
                "weight": 1000,
                "payload": {"type": "string", "value": "9000.5"},
                "weightType": "variable",
            }
        ],
        "integration-object-flag": [
            {
                "stickiness": "default",
                "name": "object-variant",
                "weight": 1000,
                "payload": {"type": "json", "value": '{"foo": "bar"}'},
                "weightType": "variable",
            }
        ],
        "integration-integer-flag": [
            {
                "stickiness": "default",
                "name": "42",
                "weight": 1000,
                "payload": {"type": "string", "value": "42"},
                "weightType": "variable",
            }
        ],
        "integration-targeting-flag": [
            {
                "stickiness": "default",
                "name": "targeted-true",
                "weight": 1000,
                "payload": {"type": "string", "value": "true"},
                "weightType": "variable",
            }
        ],
    }

    # Add targeting constraints for the targeting flag
    constraints = []
    if flag_name == "integration-targeting-flag":
        constraints = [
            {
                "contextName": "userId",
                "operator": "IN",
                "values": ["targeted-user"],
            }
        ]

    strategy_payload = {
        "name": "flexibleRollout",
        "constraints": constraints,
        "parameters": {
            "rollout": "100",
            "stickiness": "default",
            "groupId": flag_name,
        },
        "variants": variant_configs.get(flag_name, []),
        "segments": [],
        "disabled": False,
    }

    strategy_response = requests.post(
        f"{UNLEASH_URL}/api/admin/projects/default/features/{flag_name}/environments/development/strategies",
        headers=headers,
        json=strategy_payload,
        timeout=10,
    )
    if strategy_response.status_code in [200, 201]:
        logger.info(f"Strategy with variants added to '{flag_name}'")
    else:
        logger.error(
            f"Failed to add strategy to '{flag_name}': {strategy_response.status_code}"
        )


def enable_flag(flag_name: str, headers: dict):
    """Enable a flag in the development environment."""
    try:
        enable_response = requests.post(
            f"{UNLEASH_URL}/api/admin/projects/default/features/{flag_name}/environments/development/on",
            headers=headers,
            timeout=10,
        )
        if enable_response.status_code in [200, 201]:
            logger.info(f"Flag '{flag_name}' enabled in development environment")
        else:
            logger.error(
                f"Failed to enable flag '{flag_name}': {enable_response.status_code}"
            )
    except Exception as e:
        logger.error(f"Error enabling flag '{flag_name}': {e}")


EXPECTED_FLAGS = {
    "integration-boolean-flag",
    "integration-string-flag",
    "integration-float-flag",
    "integration-object-flag",
    "integration-integer-flag",
    "integration-targeting-flag",
}


def wait_for_flags_visible(timeout=30, interval=2):
    """Poll the client features endpoint until all expected flags are visible.

    After flags are created via the Admin API, there is a short propagation
    delay before they appear on the Client API.  Without this wait the
    provider's initial fetch may return stale data, causing flaky tests.
    """
    headers = {"Authorization": API_TOKEN}
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(
                f"{UNLEASH_URL}/api/client/features",
                headers=headers,
                timeout=5,
            )
            if resp.status_code == 200:
                names = {f["name"] for f in resp.json().get("features", [])}
                if EXPECTED_FLAGS.issubset(names):
                    logger.info("All flags visible via client API")
                    return
                logger.info(
                    f"Waiting for flags; have {len(names)}/{len(EXPECTED_FLAGS)}"
                )
        except Exception as e:
            logger.warning(f"Polling client features: {e}")
        time.sleep(interval)
    raise TimeoutError(f"Flags not visible via client API within {timeout}s")


@pytest.fixture(scope="session")
def postgres_container():
    """Create and start PostgreSQL container."""
    with PostgresContainer("postgres:15", driver=None) as postgres:
        postgres_url = postgres.get_connection_url()
        logger.info(f"PostgreSQL started at: {postgres_url}")

        yield postgres


def _get_container_health_url(container):
    """Get the health check URL for the container.

    Raises if port is not exposed yet.
    """
    exposed_port = container.get_exposed_port(4242)
    return f"http://localhost:{exposed_port}"


def _check_container_not_dead(container):
    """Check if container is still running, raise if dead.

    Raises RuntimeError with logs if container exited or is dead.
    """
    docker_container = container.get_wrapped_container()
    if docker_container:
        docker_container.reload()
        if docker_container.status in ("exited", "dead"):
            logs = docker_container.logs().decode(errors="replace")
            raise RuntimeError(
                f"Unleash container died ({docker_container.status}).\nLogs:\n{logs}"
            )


def _get_container_logs(container):
    """Get container logs for debugging."""
    docker_container = container.get_wrapped_container()
    if docker_container:
        docker_container.reload()
        return docker_container.logs().decode(errors="replace")
    return ""


def _log_timeout_and_logs(container):
    """Log timeout error and container logs for debugging."""
    try:
        logs = _get_container_logs(container)
        logger.error("Unleash container did not become healthy within timeout")
        if logs:
            logger.error(f"Logs:\n{logs}")
    except Exception:
        logger.exception("Failed to retrieve container logs")


def _wait_for_healthy(container, max_wait_time=120):
    """Poll the Unleash container until its /health endpoint returns 200.

    Returns the base URL on success, raises on timeout or container death.
    """
    start_time = time.time()

    while time.time() - start_time < max_wait_time:
        try:
            try:
                unleash_url = _get_container_health_url(container)
                logger.info(f"Trying health check at: {unleash_url}")
            except Exception as port_error:
                _check_container_not_dead(container)
                logger.error(f"Port not ready yet: {port_error}")
                time.sleep(2)
                continue

            response = requests.get(f"{unleash_url}/health", timeout=5)
            if response.status_code == 200:
                logger.info("Unleash container is healthy!")
                return unleash_url

            logger.error(f"Health check failed, status: {response.status_code}")
            time.sleep(2)

        except RuntimeError:
            raise
        except Exception as e:
            logger.error(f"Health check error: {e}")
            time.sleep(2)

    _log_timeout_and_logs(container)
    raise RuntimeError("Unleash container did not become healthy within timeout")


# Unleash's migration runner can hit a pg_class_relname_nsp_index race
# condition that kills the process on first start.  Retrying is safe because
# the partially-created objects already exist on the second attempt.
MAX_UNLEASH_ATTEMPTS = 3


@pytest.fixture(scope="session")
def unleash_container(postgres_container):
    """Create and start Unleash container with PostgreSQL dependency."""
    global UNLEASH_URL

    postgres_url = postgres_container.get_connection_url()
    postgres_bridge_ip = postgres_container.get_docker_client().bridge_ip(
        postgres_container._container.id
    )

    # Create internal URL using the bridge IP and internal port (5432)
    exposed_port = postgres_container.get_exposed_port(5432)
    internal_url = postgres_url.replace("localhost", postgres_bridge_ip).replace(
        f":{exposed_port}", ":5432"
    )

    last_error = None

    for attempt in range(1, MAX_UNLEASH_ATTEMPTS + 1):
        unleash = UnleashContainer(internal_url)

        with unleash as container:
            logger.info(f"Starting Unleash container (attempt {attempt})...")
            logger.info("Unleash container started")

            try:
                unleash_url = _wait_for_healthy(container)
            except RuntimeError as exc:
                last_error = exc
                if "pg_class_relname_nsp_index" in str(exc) or "died" in str(exc):
                    logger.warning(
                        f"Unleash failed on attempt {attempt} "
                        f"(likely migration race); retrying..."
                    )
                    continue
                raise

            UNLEASH_URL = unleash_url
            logger.info(f"Unleash started at: {unleash_url}")

            insert_admin_token(postgres_container)
            logger.info("Admin token inserted into database")

            yield container, unleash_url
            return

    raise RuntimeError(
        f"Unleash failed to start after {MAX_UNLEASH_ATTEMPTS} attempts"
    ) from last_error


@pytest.fixture(scope="session", autouse=True)
def setup_test_flags(unleash_container):
    """Setup test flags and wait for them to be visible via the client API."""
    logger.info("Creating test flags in Unleash...")
    create_test_flags()
    logger.info("Waiting for flags to propagate to client API...")
    wait_for_flags_visible()
    logger.info("Test flags setup completed")


@pytest.fixture(scope="session")
def unleash_provider(setup_test_flags):
    """Create an Unleash provider instance for testing."""
    provider = UnleashProvider(
        url=f"{UNLEASH_URL}/api",
        app_name="test-app",
        api_token=API_TOKEN,
    )
    provider.initialize()
    yield provider
    provider.shutdown()


@pytest.fixture(scope="session")
def client(unleash_provider):
    """Create an OpenFeature client with the Unleash provider."""
    api.set_provider(unleash_provider)
    return api.get_client()


@pytest.mark.integration
def test_integration_health_check():
    """Test that Unleash health check endpoint is accessible."""
    response = requests.get(f"{UNLEASH_URL}/health", timeout=5)
    assert response.status_code == 200


@pytest.mark.integration
def test_integration_flag_details_resolution(unleash_provider):
    """Test flag details resolution with the Unleash provider."""
    details = unleash_provider.resolve_boolean_details(
        "integration-boolean-flag", False
    )
    assert details is not None
    assert hasattr(details, "value")
    assert hasattr(details, "reason")
    assert hasattr(details, "variant")
    assert details.value is True


@pytest.mark.integration
def test_integration_boolean_flag_resolution(unleash_provider):
    """Test boolean flag resolution with the Unleash provider."""
    details = unleash_provider.resolve_boolean_details(
        "integration-boolean-flag", False
    )
    assert details.value is True


@pytest.mark.integration
def test_integration_string_flag_resolution(unleash_provider):
    """Test string flag resolution with the Unleash provider."""
    details = unleash_provider.resolve_string_details(
        "integration-string-flag", "default"
    )
    assert details.value == "my-string"


@pytest.mark.integration
def test_integration_integer_flag_resolution(unleash_provider):
    """Test integer flag resolution with the Unleash provider."""
    details = unleash_provider.resolve_integer_details("integration-integer-flag", 0)
    assert details.value == 42


@pytest.mark.integration
def test_integration_float_flag_resolution(unleash_provider):
    """Test float flag resolution with the Unleash provider."""
    details = unleash_provider.resolve_float_details("integration-float-flag", 0.0)
    assert details.value == 9000.5


@pytest.mark.integration
def test_integration_object_flag_resolution(unleash_provider):
    """Test object flag resolution with the Unleash provider."""
    details = unleash_provider.resolve_object_details("integration-object-flag", {})
    assert details.value == {"foo": "bar"}


@pytest.mark.integration
def test_integration_nonexistent_flag(unleash_provider):
    """Test that non-existent flags return default value."""
    details = unleash_provider.resolve_boolean_details("test-nonexistent-flag", False)
    assert details.value is False
    assert details.reason.value == "DEFAULT"


@pytest.mark.integration
def test_integration_targeting_positive_case(unleash_provider):
    """Test targeting with a user that should be targeted (positive case)."""
    context = EvaluationContext(targeting_key="targeted-user")

    details = unleash_provider.resolve_boolean_details(
        "integration-targeting-flag", False, context
    )
    assert details.value is True
    assert isinstance(details.value, bool)


@pytest.mark.integration
def test_integration_targeting_negative_case(unleash_provider):
    """Test targeting with a user that should not be targeted (negative case)."""
    context = EvaluationContext(targeting_key="non-targeted-user")

    details = unleash_provider.resolve_boolean_details(
        "integration-targeting-flag", False, context
    )
    assert details.value is False
    assert isinstance(details.value, bool)
