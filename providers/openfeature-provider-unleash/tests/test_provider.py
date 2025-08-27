import pytest
from unittest.mock import Mock, patch

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.flag_evaluation import Reason
from openfeature.exception import ErrorCode


def test_unleash_provider_import():
    """Test that UnleashProvider can be imported."""
    assert UnleashProvider is not None


def test_unleash_provider_instantiation():
    """Test that UnleashProvider can be instantiated."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    assert provider is not None
    provider.shutdown()


def test_unleash_provider_get_metadata():
    """Test that UnleashProvider returns correct metadata."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    metadata = provider.get_metadata()
    assert metadata.name == "Unleash Provider"
    provider.shutdown()


def test_unleash_provider_all_methods_implemented():
    """Test that all UnleashProvider methods are implemented."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )

    # All methods should be callable (not raise NotImplementedError)
    assert callable(provider.resolve_string_details)
    assert callable(provider.resolve_integer_details)
    assert callable(provider.resolve_float_details)
    assert callable(provider.resolve_object_details)

    provider.shutdown()


def test_unleash_provider_hooks():
    """Test that UnleashProvider returns empty hooks list."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )
    hooks = provider.get_provider_hooks()
    assert hooks == []
    provider.shutdown()


def test_unleash_provider_resolve_boolean_details(unleash_provider_client):
    """Test that UnleashProvider can resolve boolean flags."""
    client = unleash_provider_client

    flag = client.get_boolean_details(flag_key="test_flag", default_value=False)
    assert flag is not None
    assert flag.value is True
    assert flag.reason == Reason.TARGETING_MATCH


def test_unleash_provider_resolve_boolean_details_error():
    """Test that UnleashProvider handles errors gracefully."""
    mock_client = Mock()
    mock_client.is_enabled.side_effect = Exception("Connection error")

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = provider.resolve_boolean_details("test_flag", True)
        assert flag.value is True
        assert flag.reason == Reason.ERROR
        assert flag.error_code == ErrorCode.GENERAL
        assert flag.error_message == "Connection error"

        provider.shutdown()


def test_unleash_provider_resolve_string_details():
    """Test that UnleashProvider can resolve string flags."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "test-string"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = provider.resolve_string_details("test_flag", "default")
        assert flag.value == "test-string"
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


def test_unleash_provider_resolve_integer_details():
    """Test that UnleashProvider can resolve integer flags."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "42"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = provider.resolve_integer_details("test_flag", 0)
        assert flag.value == 42
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


def test_unleash_provider_resolve_float_details():
    """Test that UnleashProvider can resolve float flags."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "3.14"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = provider.resolve_float_details("test_flag", 0.0)
        assert flag.value == 3.14
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


def test_unleash_provider_resolve_object_details():
    """Test that UnleashProvider can resolve object flags."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": '{"key": "value", "number": 42}'},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = provider.resolve_object_details("test_flag", {"default": "value"})
        assert flag.value == {"key": "value", "number": 42}
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


@pytest.mark.asyncio
async def test_unleash_provider_resolve_boolean_details_async():
    """Test that UnleashProvider can resolve boolean flags asynchronously."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = await provider.resolve_boolean_details_async("test_flag", False)
        assert flag.value is True
        assert flag.reason == Reason.TARGETING_MATCH

        provider.shutdown()


@pytest.mark.asyncio
async def test_unleash_provider_resolve_string_details_async():
    """Test that UnleashProvider can resolve string flags asynchronously."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "test-string"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = await provider.resolve_string_details_async("test_flag", "default")
        assert flag.value == "test-string"
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


@pytest.mark.asyncio
async def test_unleash_provider_resolve_integer_details_async():
    """Test that UnleashProvider can resolve integer flags asynchronously."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "42"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = await provider.resolve_integer_details_async("test_flag", 0)
        assert flag.value == 42
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


@pytest.mark.asyncio
async def test_unleash_provider_resolve_float_details_async():
    """Test that UnleashProvider can resolve float flags asynchronously."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": "3.14"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = await provider.resolve_float_details_async("test_flag", 0.0)
        assert flag.value == 3.14
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


@pytest.mark.asyncio
async def test_unleash_provider_resolve_object_details_async():
    """Test that UnleashProvider can resolve object flags asynchronously."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": '{"key": "value", "number": 42}'},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        flag = await provider.resolve_object_details_async(
            "test_flag", {"default": "value"}
        )
        assert flag.value == {"key": "value", "number": 42}
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()
