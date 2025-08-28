"""Integration tests for Unleash provider using testcontainers."""

from datetime import datetime, timezone
import time

from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext
import psycopg2
import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

# Configuration for the running Unleash instance (will be set by fixtures)
UNLEASH_URL = None
API_TOKEN = "default:development.unleash-insecure-api-token"
ADMIN_TOKEN = "user:76672ac99726f8e48a1bbba16b7094a50d1eee3583d1e8457e12187a"


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
        self.with_env("HOST", "0.0.0.0")
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
            print("Admin token inserted successfully")
    except Exception as e:
        print(f"Error inserting admin token: {e}")
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
                print(f"Flag '{flag['name']}' created")
                add_strategy_with_variants(flag["name"], headers)
                enable_flag(flag["name"], headers)
            else:
                print(f"Failed to create flag '{flag['name']}': {response.status_code}")
        except Exception as e:
            print(f"Error creating flag '{flag['name']}': {e}")


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
        print(f"Strategy with variants added to '{flag_name}'")
    else:
        print(
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
            print(f"Flag '{flag_name}' enabled in development environment")
        else:
            print(f"Failed to enable flag '{flag_name}': {enable_response.status_code}")
    except Exception as e:
        print(f"Error enabling flag '{flag_name}': {e}")


@pytest.fixture(scope="session")
def postgres_container():
    """Create and start PostgreSQL container."""
    with PostgresContainer("postgres:15", driver=None) as postgres:
        postgres.start()
        postgres_url = postgres.get_connection_url()
        print(f"PostgreSQL started at: {postgres_url}")

        yield postgres


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

    unleash = UnleashContainer(internal_url)

    with unleash as container:
        print("Starting Unleash container...")
        container.start()
        print("Unleash container started")

        # Wait for health check to pass
        print("Waiting for Unleash container to be healthy...")
        max_wait_time = 60  # 1 minute max wait
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                # Get the exposed port
                try:
                    exposed_port = container.get_exposed_port(4242)
                    unleash_url = f"http://localhost:{exposed_port}"
                    print(f"Trying health check at: {unleash_url}")
                except Exception as port_error:
                    print(f"Port not ready yet: {port_error}")
                    time.sleep(2)
                    continue

                # Try to connect to health endpoint
                response = requests.get(f"{unleash_url}/health", timeout=5)
                if response.status_code == 200:
                    print("Unleash container is healthy!")
                    break

                print(f"Health check failed, status: {response.status_code}")
                time.sleep(2)

            except Exception as e:
                print(f"Health check error: {e}")
                time.sleep(2)
        else:
            raise Exception("Unleash container did not become healthy within timeout")

        # Get the exposed port and set global URL
        UNLEASH_URL = f"http://localhost:{container.get_exposed_port(4242)}"
        print(f"Unleash started at: {unleash_url}")

        insert_admin_token(postgres_container)
        print("Admin token inserted into database")

        yield container, unleash_url


@pytest.fixture(scope="session", autouse=True)
def setup_test_flags(unleash_container):
    """Setup test flags before running any tests."""
    print("Creating test flags in Unleash...")
    create_test_flags()
    print("Test flags setup completed")


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
    # Clean up the provider to avoid multiple UnleashClient instances
    provider.shutdown()


@pytest.fixture(scope="session")
def client(unleash_provider):
    """Create an OpenFeature client with the Unleash provider."""
    # Set the provider globally
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
