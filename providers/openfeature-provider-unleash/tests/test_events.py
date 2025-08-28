"""Tests for events functionality."""

import uuid
from unittest.mock import Mock, patch

import pytest
from UnleashClient.events import (
    UnleashEventType,
    UnleashFetchedEvent,
    UnleashReadyEvent,
)

from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.event import ProviderEvent
from openfeature.exception import GeneralError
from openfeature.provider import ProviderStatus


def test_events():
    """Test that UnleashProvider supports event handling."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        # Test event handler registration
        ready_events = []
        error_events = []
        config_events = []

        def on_ready(event_details):
            ready_events.append(event_details)

        def on_error(event_details):
            error_events.append(event_details)

        def on_config_changed(event_details):
            config_events.append(event_details)

        provider.add_handler(ProviderEvent.PROVIDER_READY, on_ready)
        provider.add_handler(ProviderEvent.PROVIDER_ERROR, on_error)
        provider.add_handler(
            ProviderEvent.PROVIDER_CONFIGURATION_CHANGED, on_config_changed
        )

        # Initialize should emit PROVIDER_READY
        provider.initialize()
        assert len(ready_events) == 1
        assert ready_events[0]["provider_name"] == "Unleash Provider"

        # Test error event emission
        mock_client.initialize_client.side_effect = Exception("Test error")
        error_provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        error_provider.add_handler(ProviderEvent.PROVIDER_ERROR, on_error)

        with pytest.raises(GeneralError):
            error_provider.initialize()

        assert len(error_events) == 1
        assert "Test error" in error_events[0]["error_message"]

        # Test handler removal
        provider.remove_handler(ProviderEvent.PROVIDER_READY, on_ready)
        provider.shutdown()  # Should not trigger ready event again


def test_unleash_event_callback():
    """Test that UnleashProvider handles UnleashClient events correctly."""
    mock_client = Mock()
    mock_client.initialize_client.return_value = None

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )

        # Initialize to trigger UnleashClient creation
        provider.initialize()

        # Capture the event callback
        event_callback = mock_unleash_client.call_args[1]["event_callback"]

        # Test UnleashReadyEvent
        ready_events = []
        provider.add_handler(
            ProviderEvent.PROVIDER_READY, lambda details: ready_events.append(details)
        )

        event_callback(UnleashReadyEvent(UnleashEventType.READY, uuid.uuid4()))
        assert len(ready_events) == 1
        assert provider.get_status() == ProviderStatus.READY

        # Test UnleashFetchedEvent
        config_events = []
        provider.add_handler(
            ProviderEvent.PROVIDER_CONFIGURATION_CHANGED,
            lambda details: config_events.append(details),
        )

        # Create a mock UnleashFetchedEvent with features
        mock_event = Mock(spec=UnleashFetchedEvent)
        mock_event.features = {"flag1": {}, "flag2": {}}

        event_callback(mock_event)
        assert len(config_events) == 1
        assert config_events[0]["flag_keys"] == ["flag1", "flag2"]

        provider.shutdown()
