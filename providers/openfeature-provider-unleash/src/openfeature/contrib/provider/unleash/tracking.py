"""Tracking functionality for Unleash provider."""

import uuid
from typing import Any, Optional, Protocol

from UnleashClient import UnleashClient
from UnleashClient.events import UnleashEvent, UnleashEventType

from openfeature.evaluation_context import EvaluationContext


class UnleashProvider(Protocol):
    """Protocol defining the interface needed by Tracker."""

    @property
    def client(self) -> Optional[UnleashClient]: ...

    def _build_unleash_context(
        self, evaluation_context: Optional[EvaluationContext] = None
    ) -> Optional[dict[str, Any]]: ...

    def _unleash_event_callback(self, event: Any) -> None: ...


class Tracker:
    """Manages tracking functionality for the Unleash provider."""

    def __init__(self, provider: UnleashProvider) -> None:
        """Initialize the tracking manager.

        Args:
            provider: The parent UnleashProvider instance
        """
        self._provider = provider

    def track(
        self,
        event_name: str,
        evaluation_context: Optional[EvaluationContext] = None,
        event_details: Optional[dict] = None,
    ) -> None:
        """Track user actions or application states using Unleash impression events.

        Args:
            event_name: The name of the tracking event
            evaluation_context: Optional evaluation context
            event_details: Optional tracking event details
        """
        if not self._provider.client:
            return

        unleash_context = (
            self._provider._build_unleash_context(evaluation_context) or {}
        )

        if event_details:
            unleash_context.update(
                {
                    "tracking_value": event_details.get("value"),
                    "tracking_details": event_details,
                }
            )

        tracking_event = UnleashEvent(
            event_type=UnleashEventType.FEATURE_FLAG,
            event_id=uuid.uuid4(),
            context=unleash_context,
            enabled=True,
            feature_name=event_name,
            variant="tracking_event",
        )

        if hasattr(self._provider, "_unleash_event_callback"):
            self._provider._unleash_event_callback(tracking_event)
