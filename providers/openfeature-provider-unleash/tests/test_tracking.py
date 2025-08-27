"""Tests for tracking functionality."""

from unittest.mock import Mock, patch

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext


def test_track_basic():
    """Test basic tracking functionality."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        # Set the event callback
        provider._unleash_event_callback = mock_event_callback

        # Track a basic event
        provider.track("user_action")

        # Verify the tracking event was created and passed to callback
        assert mock_event_callback.call_count == 1
        tracking_event = mock_event_callback.call_args[0][0]
        assert tracking_event.feature_name == "user_action"
        assert tracking_event.enabled is True
        assert tracking_event.variant == "tracking_event"

        provider.shutdown()


def test_track_with_context():
    """Test tracking with evaluation context."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        provider._unleash_event_callback = mock_event_callback

        context = EvaluationContext(
            targeting_key="user123",
            attributes={"email": "user@example.com", "role": "admin"},
        )

        provider.track("page_view", context)

        tracking_event = mock_event_callback.call_args[0][0]
        assert tracking_event.context["userId"] == "user123"
        assert tracking_event.context["email"] == "user@example.com"
        assert tracking_event.context["role"] == "admin"

        provider.shutdown()


def test_track_with_event_details():
    """Test tracking with event details."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        provider._unleash_event_callback = mock_event_callback

        event_details = {"value": 99.99, "currency": "USD", "category": "purchase"}

        provider.track("purchase_completed", event_details=event_details)

        tracking_event = mock_event_callback.call_args[0][0]
        assert tracking_event.context["tracking_value"] == 99.99
        assert tracking_event.context["tracking_details"] == event_details

        provider.shutdown()


def test_track_not_initialized():
    """Test tracking when provider is not initialized."""
    provider = UnleashProvider(
        url="http://localhost:4242", app_name="test-app", api_token="test-token"
    )

    # Should not raise any exception, just return
    provider.track("test_event")


def test_track_edge_cases():
    """Test tracking edge cases."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        provider._unleash_event_callback = mock_event_callback

        # Test event details without value
        event_details = {"category": "test", "action": "view"}
        provider.track("test_event", event_details=event_details)
        tracking_event = mock_event_callback.call_args[0][0]
        assert tracking_event.context["tracking_value"] is None
        assert tracking_event.context["tracking_details"] == event_details

        provider.shutdown()


def test_track_none_context():
    """Test tracking with None context."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        provider._unleash_event_callback = mock_event_callback

        provider.track("test_event", None)

        tracking_event = mock_event_callback.call_args[0][0]
        assert tracking_event.context == {}

        provider.shutdown()


def test_track_none_event_details():
    """Test tracking with None event details."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None
    mock_event_callback = Mock()

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        provider.initialize()

        provider._unleash_event_callback = mock_event_callback

        provider.track("test_event", event_details=None)

        tracking_event = mock_event_callback.call_args[0][0]
        assert "tracking_value" not in tracking_event.context
        assert "tracking_details" not in tracking_event.context

        provider.shutdown()
