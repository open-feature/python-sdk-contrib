"""Events functionality for Unleash provider."""

from contextlib import suppress
from typing import Any, Callable, Protocol

from UnleashClient.events import BaseEvent, UnleashEventType

from openfeature.event import ProviderEvent
from openfeature.provider import Metadata


class UnleashProvider(Protocol):
    """Protocol defining the interface expected from UnleashProvider for events."""

    @property
    def _event_handlers(self) -> dict[ProviderEvent, list[Callable]]:
        """Event handlers dictionary."""
        ...

    def get_metadata(self) -> Metadata:
        """Get provider metadata."""
        ...


class EventManager:
    """Manages events and hooks for the Unleash provider."""

    def __init__(self, provider: UnleashProvider) -> None:
        """Initialize the EventManager.

        Args:
            provider: The UnleashProvider instance
        """
        self._provider = provider

    def add_handler(self, event_type: ProviderEvent, handler: Callable) -> None:
        """Add an event handler for a specific event type.

        Args:
            event_type: The type of event to handle
            handler: The handler function to call
        """
        if event_type in self._provider._event_handlers:
            self._provider._event_handlers[event_type].append(handler)

    def remove_handler(self, event_type: ProviderEvent, handler: Callable) -> None:
        """Remove an event handler for a specific event type.

        Args:
            event_type: The type of event to handle
            handler: The handler function to remove
        """
        if (
            event_type in self._provider._event_handlers
            and handler in self._provider._event_handlers[event_type]
        ):
            self._provider._event_handlers[event_type].remove(handler)

    def emit_event(self, event_type: ProviderEvent, **kwargs: Any) -> None:
        """Emit an event to all registered handlers.

        Args:
            event_type: The type of event to emit
            **kwargs: Additional event data
        """
        if event_type in self._provider._event_handlers:
            event_details = {
                "provider_name": self._provider.get_metadata().name,
                **kwargs,
            }
            for handler in self._provider._event_handlers[event_type]:
                with suppress(Exception):
                    handler(event_details)

    def handle_unleash_event(self, event: BaseEvent) -> None:
        """Handle UnleashClient events and translate them to OpenFeature events.

        Args:
            event: The Unleash event
        """
        if event.event_type == UnleashEventType.READY:
            self.emit_event(ProviderEvent.PROVIDER_READY)
        elif event.event_type == UnleashEventType.FETCHED:
            flag_keys = []
            if hasattr(event, "features"):
                if isinstance(event.features, dict):
                    flag_keys = list(event.features.keys())
                elif isinstance(event.features, list):
                    flag_keys = [
                        feature.get("name", "")
                        for feature in event.features
                        if isinstance(feature, dict)
                    ]

            self.emit_event(
                ProviderEvent.PROVIDER_CONFIGURATION_CHANGED,
                flag_keys=flag_keys,
            )
