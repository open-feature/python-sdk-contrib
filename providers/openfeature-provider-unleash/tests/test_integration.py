"""Integration tests for Unleash provider using a running Unleash instance."""

from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext
import pytest
import requests


UNLEASH_URL = "http://0.0.0.0:4242/api"
API_TOKEN = "default:development.unleash-insecure-api-token"
ADMIN_TOKEN = "user:76672ac99726f8e48a1bbba16b7094a50d1eee3583d1e8457e12187a"


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
                f"{UNLEASH_URL}/admin/projects/default/features",
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
        f"{UNLEASH_URL}/admin/projects/default/features/{flag_name}/environments/development/strategies",
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
            f"{UNLEASH_URL}/admin/projects/default/features/{flag_name}/environments/development/on",
            headers=headers,
            timeout=10,
        )
        if enable_response.status_code in [200, 201]:
            print(f"Flag '{flag_name}' enabled in development environment")
        else:
            print(f"Failed to enable flag '{flag_name}': {enable_response.status_code}")
    except Exception as e:
        print(f"Error enabling flag '{flag_name}': {e}")


@pytest.fixture(scope="session", autouse=True)
def setup_test_flags():
    """Setup test flags before running any tests."""
    print("Creating test flags in Unleash...")
    create_test_flags()
    print("Test flags setup completed")


@pytest.fixture
def unleash_provider():
    """Create an Unleash provider instance for testing."""
    provider = UnleashProvider(
        url=UNLEASH_URL,
        app_name="test-app",
        api_token=API_TOKEN,
    )
    provider.initialize()
    yield provider
    # Clean up the provider to avoid multiple UnleashClient instances
    provider.shutdown()


@pytest.fixture
def client(unleash_provider):
    """Create an OpenFeature client with the Unleash provider."""
    # Set the provider globally
    api.set_provider(unleash_provider)
    return api.get_client()


@pytest.mark.integration
def test_integration_health_check():
    """Test that Unleash health check endpoint is accessible."""
    response = requests.get(f"{UNLEASH_URL.replace('/api', '')}/health", timeout=5)
    assert response.status_code == 200


@pytest.mark.integration
def test_integration_provider_initialization(unleash_provider):
    """Test that the Unleash provider can be initialized."""
    assert unleash_provider is not None
    assert unleash_provider.client is not None


@pytest.mark.integration
def test_integration_provider_metadata(unleash_provider):
    """Test that the provider returns correct metadata."""
    metadata = unleash_provider.get_metadata()
    assert metadata.name == "Unleash Provider"


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
def test_integration_provider_status(unleash_provider):
    """Test that the provider status is correctly reported."""
    status = unleash_provider.get_status()
    assert status.value == "READY"


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
