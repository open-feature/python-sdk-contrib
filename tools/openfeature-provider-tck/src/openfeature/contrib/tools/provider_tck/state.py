"""Per-scenario state: what a scenario accumulates, and how it observes events.

Separate from :mod:`plugin` so the step modules can import these types at the top
level. The step modules are loaded by the plugin as plugins in their own right,
and a step importing from the plugin module that loads it reads like a cycle even
where it is not one.
"""

from __future__ import annotations

import queue
import typing
from dataclasses import dataclass, field

from openfeature.client import OpenFeatureClient
from openfeature.event import EventDetails, ProviderEvent
from openfeature.flag_evaluation import FlagType

from .config import TckConfig

__all__ = ["EvaluationRecord", "EventRecorder", "TckState"]


@dataclass
class EvaluationRecord:
    """The outcome of one flag evaluation, flattened across the five typed calls."""

    value: typing.Any = None
    variant: str | None = None
    reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raised: BaseException | None = None
    """The exception the call raised, if any.

    In Python an errored evaluation returns the code default in the details
    rather than raising, so this stays ``None`` on the error paths the suite
    exercises. It is what "no exception should have been thrown" asserts.
    """


class EventRecorder:
    """Captures the events of one type, in order, so a scenario consumes them one at a time.

    Consuming rather than merely observing is what makes the stale scenario
    work: it awaits a ``PROVIDER_READY`` at the start and a second, different
    ``PROVIDER_READY`` once the backend is back, and a recorder that only
    remembered "ready has fired at some point" would report the second assertion
    as satisfied by the first event.

    A queue rather than a list because a provider with a background thread --
    anything with a real backend -- delivers events from that thread while the
    scenario waits on the main one.
    """

    def __init__(self, client: OpenFeatureClient, event: ProviderEvent) -> None:
        self.event = event
        self._client = client
        self._events: queue.Queue[EventDetails] = queue.Queue()
        self.last: EventDetails | None = None

        # The SDK replays a matching event on registration when the provider is
        # already in the corresponding state, so a handler added after the
        # provider became ready still observes its PROVIDER_READY. That is what
        # lets the feature files register handlers after "Given a stable
        # provider" without racing it.
        client.add_handler(event, self._on_event)

    def _on_event(self, details: EventDetails) -> None:
        self._events.put(details)

    def await_event(self, timeout: float) -> EventDetails:
        """Consume the next event of this recorder's type."""
        try:
            details = self._events.get(timeout=timeout)
        except queue.Empty:
            msg = (
                f"timed out after {timeout}s waiting for a {self.event.value} event. "
                f"If the provider is simply slower than this to notice, raise "
                f"TckConfig.event_timeout rather than treating it as a failure"
            )
            raise AssertionError(msg) from None
        self.last = details
        return details

    def detach(self) -> None:
        self._client.remove_handler(self.event, self._on_event)


@dataclass
class TckState:
    """Everything one scenario accumulates."""

    config: TckConfig
    client: OpenFeatureClient | None = None
    flag_key: str | None = None
    flag_type: FlagType | None = None
    default_value: typing.Any = None
    last: EvaluationRecord | None = None
    remembered: typing.Any = None
    has_memory: bool = False
    recorders: dict[ProviderEvent, EventRecorder] = field(default_factory=dict)

    def require_client(self) -> OpenFeatureClient:
        if self.client is None:
            msg = (
                "no provider has been registered in this scenario: a "
                '"Given a stable provider" or "Given a unavailable provider" step '
                "must come first"
            )
            raise AssertionError(msg)
        return self.client

    def require_flag(self) -> tuple[str, FlagType, typing.Any]:
        if self.flag_key is None or self.flag_type is None:
            msg = (
                "no flag has been declared in this scenario: a "
                '"Given a <type>-flag with key ... and a default value ..." step '
                "must come first"
            )
            raise AssertionError(msg)
        return self.flag_key, self.flag_type, self.default_value

    def require_evaluation(self) -> EvaluationRecord:
        if self.last is None:
            msg = (
                "no flag has been evaluated in this scenario: a "
                '"When the flag was evaluated with details" step must come first'
            )
            raise AssertionError(msg)
        return self.last

    def require_recorder(self, event: ProviderEvent) -> EventRecorder:
        recorder = self.recorders.get(event)
        if recorder is None:
            msg = (
                f"no handler was registered for {event.value} in this scenario: a "
                '"Given a <kind> event handler" step must come first'
            )
            raise AssertionError(msg)
        return recorder

    def teardown(self) -> None:
        for recorder in self.recorders.values():
            recorder.detach()
        self.recorders.clear()
