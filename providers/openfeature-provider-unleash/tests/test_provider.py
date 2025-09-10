import uuid
from unittest.mock import Mock, patch

from UnleashClient.events import UnleashEventType, UnleashReadyEvent

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.provider import ProviderStatus


# Mock feature response for testing cache functionality
MOCK_FEATURE_RESPONSE = {
    "version": 1,
    "features": [
        {
            "name": "testFlag",
            "description": "This is a test!",
            "enabled": True,
            "strategies": [{"name": "default", "parameters": {}}],
            "createdAt": "2018-10-04T01:27:28.477Z",
            "impressionData": True,
        },
        {
            "name": "testFlag2",
            "description": "Test flag 2",
            "enabled": False,
            "strategies": [
                {"name": "gradualRolloutRandom", "parameters": {"percentage": "50"}}
            ],
            "createdAt": "2018-10-04T11:03:56.062Z",
            "impressionData": False,
        },
    ],
}


def test_unleash_provider_import():
    """Test that UnleashProvider can be imported."""
    assert UnleashProvider is not None


def test_unleash_provider_instantiation():
    """Test that UnleashProvider can be instantiated."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    assert provider is not None
    assert provider.get_status() == ProviderStatus.NOT_READY
    provider.shutdown()


def test_unleash_provider_get_metadata():
    """Test that UnleashProvider returns correct metadata."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    metadata = provider.get_metadata()
    assert metadata.name == "Unleash Provider"
    provider.shutdown()


def test_unleash_provider_initialization():
    """Test that UnleashProvider can be initialized properly."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        # Should start as NOT_READY
        assert provider.get_status() == ProviderStatus.NOT_READY

        provider.initialize()

        # Simulate the READY event from UnleashClient
        event_callback = mock_unleash_client.call_args[1]["event_callback"]
        event_callback(UnleashReadyEvent(UnleashEventType.READY, uuid.uuid4()))

        # Should be READY after receiving the READY event
        assert provider.get_status() == ProviderStatus.READY
        assert provider.client is not None

        provider.shutdown()


def test_unleash_provider_all_methods_implemented():
    """Test that all required methods are implemented."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        # Test that all required methods exist
        assert hasattr(provider, "get_metadata")
        assert hasattr(provider, "resolve_boolean_details")
        assert hasattr(provider, "resolve_string_details")
        assert hasattr(provider, "resolve_integer_details")
        assert hasattr(provider, "resolve_float_details")
        assert hasattr(provider, "resolve_object_details")
        assert hasattr(provider, "initialize")
        assert hasattr(provider, "get_status")
        assert hasattr(provider, "shutdown")
        assert hasattr(provider, "on_context_changed")
        assert hasattr(provider, "add_handler")
        assert hasattr(provider, "remove_handler")
        assert hasattr(provider, "track")

        provider.shutdown()


def test_unleash_provider_hooks():
    """Test that UnleashProvider returns empty hooks list."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    hooks = provider.get_provider_hooks()
    assert hooks == []
    provider.shutdown()


def test_unleash_provider_context_changed():
    """Test that UnleashProvider handles context changes correctly."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )

    # Initially no context
    assert provider._last_context is None

    # Set initial context
    context1 = EvaluationContext(targeting_key="user1", attributes={"role": "admin"})
    provider.on_context_changed(None, context1)
    assert provider._last_context == context1

    # Change context
    context2 = EvaluationContext(targeting_key="user2", attributes={"role": "user"})
    provider.on_context_changed(context1, context2)
    assert provider._last_context == context2

    # Clear context
    provider.on_context_changed(context2, None)
    assert provider._last_context is None

    provider.shutdown()


def test_unleash_provider_flag_metadata():
    """Test that UnleashProvider includes flag metadata in resolution details."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "test-value"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        # Test boolean flag metadata
        result = provider.resolve_boolean_details("test_flag", False)
        assert result.flag_metadata["source"] == "unleash"
        assert result.flag_metadata["enabled"] is True
        assert result.flag_metadata["app_name"] == "test-app"

        # Test variant flag metadata
        result = provider.resolve_string_details("test_flag", "default")
        assert result.flag_metadata["source"] == "unleash"
        assert result.flag_metadata["enabled"] is True
        assert result.flag_metadata["variant_name"] == "test-variant"
        assert result.flag_metadata["app_name"] == "test-app"

        provider.shutdown()


def test_unleash_provider_with_custom_cache():
    """Test that UnleashProvider properly uses a custom cache with mocked features."""
    from UnleashClient.cache import FileCache

    # Create a custom cache with mocked features
    custom_cache = FileCache("test-app")
    custom_cache.bootstrap_from_dict(MOCK_FEATURE_RESPONSE)

    # Create provider with custom cache
    provider = UnleashProvider(
        url="http://localhost:4242",
        app_name="test-app",
        api_token="test-token",
        cache=custom_cache,
        fetch_toggles=False,
    )

    # Verify cache was stored
    assert provider.cache is custom_cache

    # Initialize the provider with fetch_toggles=False to prevent server connection
    provider.initialize()

    # Verify the provider is ready
    assert provider.get_status() == ProviderStatus.READY
    assert provider.client is not None

    # Test flag evaluation using the cached features
    # testFlag should be enabled (True in mock data)
    result = provider.resolve_boolean_details("testFlag", False)
    assert result.value is True
    assert result.reason.value == "TARGETING_MATCH"

    # testFlag2 should be disabled (False in mock data)
    result = provider.resolve_boolean_details("testFlag2", True)
    assert result.value is False
    assert result.reason.value == "DEFAULT"

    # Test string resolution with default value for non-existent flag
    result = provider.resolve_string_details("nonExistentFlag", "default_value")
    assert result.value == "default_value"
    assert result.reason.value == "DEFAULT"

    provider.shutdown()
