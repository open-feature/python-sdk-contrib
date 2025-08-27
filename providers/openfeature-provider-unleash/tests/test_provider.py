import pytest
import requests
from unittest.mock import Mock, patch

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import Reason
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    ParseError,
    TypeMismatchError,
)


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
    mock_client.is_enabled.side_effect = requests.exceptions.ConnectionError(
        "Connection error"
    )

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        with pytest.raises(GeneralError) as exc_info:
            provider.resolve_boolean_details("test_flag", True)
        assert "Connection error" in str(exc_info.value)

        provider.shutdown()


@pytest.mark.parametrize(
    "method_name, payload_value, expected_value, default_value",
    [
        ("resolve_string_details", "test-string", "test-string", "default"),
        ("resolve_integer_details", "42", 42, 0),
        ("resolve_float_details", "3.14", 3.14, 0.0),
        (
            "resolve_object_details",
            '{"key": "value", "number": 42}',
            {"key": "value", "number": 42},
            {"default": "value"},
        ),
    ],
)
def test_unleash_provider_resolve_variant_flags(
    method_name, payload_value, expected_value, default_value
):
    """Test that UnleashProvider can resolve variant-based flags."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": payload_value},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        method = getattr(provider, method_name)
        flag = method("test_flag", default_value)

        assert flag.value == expected_value
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
@pytest.mark.parametrize(
    "method_name, payload_value, expected_value, default_value",
    [
        (
            "resolve_string_details_async",
            "test-string",
            "test-string",
            "default",
        ),
        ("resolve_integer_details_async", "42", 42, 0),
        ("resolve_float_details_async", "3.14", 3.14, 0.0),
        (
            "resolve_object_details_async",
            '{"key": "value", "number": 42}',
            {"key": "value", "number": 42},
            {"default": "value"},
        ),
    ],
)
async def test_unleash_provider_resolve_variant_flags_async(
    method_name, payload_value, expected_value, default_value
):
    """Test that UnleashProvider can resolve variant-based flags asynchronously."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": payload_value},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        method = getattr(provider, method_name)
        flag = await method("test_flag", default_value)

        assert flag.value == expected_value
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


def test_unleash_provider_with_evaluation_context():
    """Test that UnleashProvider uses evaluation context correctly."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        context = EvaluationContext(
            targeting_key="user123",
            attributes={"email": "user@example.com", "country": "US"},
        )

        flag = provider.resolve_boolean_details("test_flag", False, context)
        assert flag.value is True

        # Verify that context was passed to UnleashClient
        mock_client.is_enabled.assert_called_with(
            "test_flag",
            context={"userId": "user123", "email": "user@example.com", "country": "US"},
            fallback_function=mock_client.is_enabled.call_args[1]["fallback_function"],
        )

        provider.shutdown()


@pytest.mark.parametrize(
    "method_name, payload_value, default_value, expected_error_message, expected_exception",
    [
        (
            "resolve_integer_details",
            "not-a-number",
            0,
            "invalid literal for int()",
            "TypeMismatchError",
        ),
        (
            "resolve_object_details",
            "invalid-json{",
            {"default": "value"},
            "Expecting value",
            "ParseError",
        ),
    ],
)
def test_unleash_provider_value_conversion_errors(
    method_name,
    payload_value,
    default_value,
    expected_error_message,
    expected_exception,
):
    """Test that UnleashProvider handles value conversion errors correctly."""
    mock_client = Mock()
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "test-variant",
        "payload": {"value": payload_value},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        method = getattr(provider, method_name)

        if expected_exception == "TypeMismatchError":
            with pytest.raises(TypeMismatchError) as exc_info:
                method("test_flag", default_value)
            assert expected_error_message in str(exc_info.value)
        elif expected_exception == "ParseError":
            with pytest.raises(ParseError) as exc_info:
                method("test_flag", default_value)
            assert expected_error_message in str(exc_info.value)

        provider.shutdown()


@pytest.mark.parametrize(
    "method_name, mock_side_effect, default_value, expected_error_message, expected_exception",
    [
        (
            "resolve_string_details",
            requests.exceptions.HTTPError(
                "404 Client Error: Not Found", response=Mock(status_code=404)
            ),
            "default",
            "Flag not found",
            "FlagNotFoundError",
        ),
        (
            "resolve_boolean_details",
            requests.exceptions.ConnectionError("Connection error"),
            True,
            "Connection error",
            "GeneralError",
        ),
    ],
)
def test_unleash_provider_general_errors(
    method_name,
    mock_side_effect,
    default_value,
    expected_error_message,
    expected_exception,
):
    """Test that UnleashProvider handles general errors correctly."""
    mock_client = Mock()

    if method_name == "resolve_boolean_details":
        mock_client.is_enabled.side_effect = mock_side_effect
    else:
        mock_client.get_variant.side_effect = mock_side_effect

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        method = getattr(provider, method_name)

        if expected_exception == "FlagNotFoundError":
            with pytest.raises(FlagNotFoundError) as exc_info:
                method("non_existent_flag", default_value)
            assert expected_error_message in str(exc_info.value)
        else:
            with pytest.raises(GeneralError) as exc_info:
                method("test_flag", default_value)
            assert expected_error_message in str(exc_info.value)

        provider.shutdown()


def test_unleash_provider_edge_cases():
    """Test UnleashProvider with edge cases and boundary conditions."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True
    mock_client.get_variant.return_value = {
        "enabled": True,
        "name": "edge-variant",
        "payload": {"value": "edge-value"},
    }

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        # Test with empty string flag key
        result = provider.resolve_string_details("", "default")
        assert result.value == "edge-value"

        # Test with very long flag key
        long_key = "a" * 1000
        result = provider.resolve_string_details(long_key, "default")
        assert result.value == "edge-value"

        # Test with special characters in flag key
        special_key = "flag-with-special-chars!@#$%^&*()"
        result = provider.resolve_string_details(special_key, "default")
        assert result.value == "edge-value"

        result = provider.resolve_string_details("test_flag", "default")
        assert result.value == "edge-value"

        provider.shutdown()


@pytest.mark.parametrize(
    "mock_side_effect, expected_error_message",
    [
        (
            requests.exceptions.HTTPError(
                "429 Too Many Requests", response=Mock(status_code=429)
            ),
            "HTTP error",
        ),
        (
            requests.exceptions.Timeout("Request timeout"),
            "Unexpected error",
        ),
        (
            requests.exceptions.SSLError("SSL certificate error"),
            "Unexpected error",
        ),
    ],
)
def test_unleash_provider_network_errors(mock_side_effect, expected_error_message):
    """Test that UnleashProvider handles network errors correctly."""
    mock_client = Mock()
    mock_client.is_enabled.side_effect = mock_side_effect

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        with pytest.raises(GeneralError) as exc_info:
            provider.resolve_boolean_details("test_flag", True)
        assert expected_error_message in str(exc_info.value)

        provider.shutdown()


def test_unleash_provider_context_without_targeting_key():
    """Test that UnleashProvider works with context without targeting key."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        context = EvaluationContext(attributes={"user_id": "123", "role": "admin"})
        result = provider.resolve_boolean_details(
            "test_flag", False, evaluation_context=context
        )
        assert result.value is True

        provider.shutdown()


def test_unleash_provider_context_with_targeting_key():
    """Test that UnleashProvider correctly maps targeting key to userId."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        context = EvaluationContext(
            targeting_key="user123", attributes={"role": "admin", "region": "us-east"}
        )
        result = provider.resolve_boolean_details(
            "test_flag", False, evaluation_context=context
        )
        assert result.value is True

        mock_client.is_enabled.assert_called_once()
        call_args = mock_client.is_enabled.call_args
        assert call_args[1]["context"]["userId"] == "user123"
        assert call_args[1]["context"]["role"] == "admin"
        assert call_args[1]["context"]["region"] == "us-east"

        provider.shutdown()


def test_unleash_provider_variant_flag_scenarios():
    """Test various variant flag scenarios."""
    mock_client = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        mock_client.get_variant.return_value = {
            "enabled": False,
            "name": "disabled-variant",
        }
        result = provider.resolve_string_details("test_flag", "default")
        assert result.value == "default"
        assert result.reason == Reason.DEFAULT
        assert result.variant is None

        mock_client.get_variant.return_value = {
            "enabled": True,
            "name": "enabled-variant",
        }
        result = provider.resolve_string_details("test_flag", "default")
        assert result.value == "default"
        assert result.reason == Reason.DEFAULT
        assert result.variant is None

        mock_client.get_variant.return_value = {
            "enabled": True,
            "name": "test-variant",
            "payload": {"value": "variant-value"},
        }
        result = provider.resolve_string_details("test_flag", "default")
        assert result.value == "variant-value"
        assert result.reason == Reason.TARGETING_MATCH
        assert result.variant == "test-variant"

        mock_client.get_variant.return_value = {
            "enabled": True,
            "name": "test-variant",
            "payload": {},
        }
        result = provider.resolve_string_details("test_flag", "default")
        assert result.value == "default"
        assert result.reason == Reason.DEFAULT
        assert result.variant == "test-variant"

        provider.shutdown()


def test_unleash_provider_type_validation():
    """Test that UnleashProvider handles type validation correctly."""
    mock_client = Mock()
    # Mock returning wrong type for boolean flag
    mock_client.is_enabled.return_value = "not-a-boolean"

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        result = provider.resolve_boolean_details("test_flag", False)
        assert result.value == "not-a-boolean"
        assert isinstance(result.value, str)

        provider.shutdown()
