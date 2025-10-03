from collections.abc import Mapping, Sequence
from typing import Any, Callable, Optional, Union

from UnleashClient import UnleashClient
from UnleashClient.cache import BaseCache
from UnleashClient.events import BaseEvent, UnleashEventType

from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEvent
from openfeature.exception import ErrorCode, GeneralError
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata, ProviderStatus

from .events import EventManager
from .flag_evaluation import FlagEvaluator

__all__ = ["UnleashProvider"]


class UnleashProvider(AbstractProvider):
    def __init__(
        self,
        url: str,
        app_name: str,
        api_token: str,
        fetch_toggles: bool = True,
        cache: Optional[BaseCache] = None,
    ) -> None:
        """Initialize the Unleash provider.

        Args:
            url: The Unleash API URL
            app_name: The application name
            api_token: The API token for authentication
            fetch_toggles: Whether to fetch toggles from server on initialization (default: True)
            cache: Optional cache implementation to use (default: UnleashClient's default)
        """
        self.url = url
        self.app_name = app_name
        self.api_token = api_token
        self.cache = cache
        self._status = ProviderStatus.NOT_READY

        self.client: UnleashClient = UnleashClient(
            url=self.url,
            app_name=self.app_name,
            custom_headers={"Authorization": self.api_token},
            event_callback=self._unleash_event_callback,
            cache=self.cache,
        )
        self._last_context: Optional[EvaluationContext] = None
        self._event_handlers: dict[ProviderEvent, list[Callable]] = {
            ProviderEvent.PROVIDER_READY: [],
            ProviderEvent.PROVIDER_ERROR: [],
            ProviderEvent.PROVIDER_CONFIGURATION_CHANGED: [],
            ProviderEvent.PROVIDER_STALE: [],
        }
        self._event_manager = EventManager(self)
        self._flag_evaluator = FlagEvaluator(self)
        self.fetch_toggles = fetch_toggles

    def initialize(
        self, evaluation_context: Optional[EvaluationContext] = None
    ) -> None:
        """Initialize the Unleash provider.

        Args:
            evaluation_context: Optional evaluation context (not used for initialization)
        """
        try:
            self.client.initialize_client(fetch_toggles=self.fetch_toggles)
        except Exception as e:
            self._status = ProviderStatus.ERROR
            self._event_manager.emit_event(
                ProviderEvent.PROVIDER_ERROR,
                error_message=str(e),
                error_code=ErrorCode.GENERAL,
            )
            raise GeneralError(f"Failed to initialize Unleash provider: {e}") from e

    def get_status(self) -> ProviderStatus:
        """Get the current status of the provider."""
        return self._status

    def get_metadata(self) -> Metadata:
        """Get provider metadata."""
        return Metadata(name="Unleash Provider")

    def get_provider_hooks(self) -> list[Hook]:
        """Get provider hooks."""
        return []

    def shutdown(self) -> None:
        """Shutdown the Unleash client."""
        if self.client.is_initialized:
            self.client.destroy()
        self._status = ProviderStatus.NOT_READY

    def on_context_changed(
        self,
        old_context: Optional[EvaluationContext],
        new_context: Optional[EvaluationContext],
    ) -> None:
        """Handle evaluation context changes.

        Args:
            old_context: The previous evaluation context
            new_context: The new evaluation context
        """
        self._last_context = new_context

    def add_handler(self, event_type: ProviderEvent, handler: Callable) -> None:
        """Add an event handler for a specific event type.

        Args:
            event_type: The type of event to handle
            handler: The handler function to call
        """
        self._event_manager.add_handler(event_type, handler)

    def remove_handler(self, event_type: ProviderEvent, handler: Callable) -> None:
        """Remove an event handler for a specific event type.

        Args:
            event_type: The type of event to handle
            handler: The handler function to remove
        """
        self._event_manager.remove_handler(event_type, handler)

    def _unleash_event_callback(self, event: BaseEvent) -> None:
        """Callback for UnleashClient events.

        Args:
            event: The Unleash event
        """
        if event.event_type == UnleashEventType.READY:
            self._status = ProviderStatus.READY
        self._event_manager.handle_unleash_event(event)

    def track(
        self,
        event_name: str,
        event_details: Optional[dict] = None,
    ) -> None:
        """No-op tracking method.

        Tracking is not implemented for this provider. Per the OpenFeature spec,
        when the provider doesn't support tracking, client.track calls should no-op.
        """
        return None

    def _build_unleash_context(
        self, evaluation_context: Optional[EvaluationContext] = None
    ) -> Optional[dict[str, Any]]:
        """Convert OpenFeature evaluation context to Unleash context."""
        if not evaluation_context:
            return None

        context: dict[str, Any] = {}
        if evaluation_context.targeting_key:
            context["userId"] = evaluation_context.targeting_key
        context.update(evaluation_context.attributes)
        return context

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details."""
        return self._flag_evaluator.resolve_boolean_details(
            flag_key, default_value, evaluation_context
        )

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve string flag details."""
        return self._flag_evaluator.resolve_string_details(
            flag_key, default_value, evaluation_context
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details."""
        return self._flag_evaluator.resolve_integer_details(
            flag_key, default_value, evaluation_context
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details."""
        return self._flag_evaluator.resolve_float_details(
            flag_key, default_value, evaluation_context
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        """Resolve object flag details."""
        return self._flag_evaluator.resolve_object_details(
            flag_key, default_value, evaluation_context
        )
