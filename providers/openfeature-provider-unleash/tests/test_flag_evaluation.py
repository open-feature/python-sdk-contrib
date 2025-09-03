"""Tests for flag evaluation functionality."""

from unittest.mock import Mock, patch

import pytest

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import Reason


def test_resolve_boolean_details():
    """Test that FlagEvaluator can resolve boolean flags."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        flag = provider.resolve_boolean_details("test_flag", False)
        assert flag is not None
        assert flag.value is True
        assert flag.reason == Reason.TARGETING_MATCH


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
def test_resolve_variant_flags(
    method_name, payload_value, expected_value, default_value
):
    """Test that FlagEvaluator can resolve variant-based flags."""
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
        provider.initialize()

        method = getattr(provider, method_name)
        flag = method("test_flag", default_value)

        assert flag.value == expected_value
        assert flag.reason == Reason.TARGETING_MATCH
        assert flag.variant == "test-variant"

        provider.shutdown()


def test_with_evaluation_context():
    """Test that FlagEvaluator uses evaluation context correctly."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        context = EvaluationContext(
            targeting_key="user123",
            attributes={"email": "user@example.com", "country": "US"},
        )

        flag = provider.resolve_boolean_details("test_flag", False, context)
        assert flag.value is True

        mock_client.is_enabled.assert_called_with(
            "test_flag",
            context={"userId": "user123", "email": "user@example.com", "country": "US"},
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
def test_value_conversion_errors(
    method_name,
    payload_value,
    default_value,
    expected_error_message,
    expected_exception,
):
    """Test that FlagEvaluator handles value conversion errors correctly."""
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
        provider.initialize()

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


def test_edge_cases():
    """Test FlagEvaluator with edge cases and boundary conditions."""
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
        provider.initialize()

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


def test_context_without_targeting_key():
    """Test that FlagEvaluator works with context without targeting key."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        context = EvaluationContext(attributes={"user_id": "123", "role": "admin"})
        result = provider.resolve_boolean_details(
            "test_flag", False, evaluation_context=context
        )
        assert result.value is True

        provider.shutdown()


def test_context_with_targeting_key():
    """Test that FlagEvaluator correctly maps targeting key to userId."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

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


def test_variant_flag_scenarios():
    """Test various variant flag scenarios."""
    mock_client = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

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
        assert result.reason == Reason.TARGETING_MATCH
        assert result.variant == "test-variant"

        provider.shutdown()


def test_type_validation():
    """Test that FlagEvaluator handles type validation correctly."""
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
        provider.initialize()

        result = provider.resolve_boolean_details("test_flag", False)
        assert result.value == "not-a-boolean"
        assert isinstance(result.value, str)

        provider.shutdown()
