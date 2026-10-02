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
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import EventDetails, ProviderEvent
from openfeature.flag_evaluation import FlagType
from openfeature.provider import FeatureProvider

from .config import TckConfig

__all__ = ["EvaluationRecord", "EventRecorder", "LifecycleRecord", "TckState"]


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


@dataclass
class LifecycleRecord:
    """The outcome of one direct call into the provider's lifecycle.

    The shutdown scenarios call the provider's own ``shutdown`` and
    ``initialize`` rather than going through the SDK, because the SDK's
    bookkeeping around them is Appendix B's business rather than this suite's.
    Each call is recorded the same way an evaluation is -- what it raised, if
    anything -- so that "no exception should have been thrown" reads one kind
    of record for both, plus how long it took, which is what the prompt-shutdown
    scenario bounds.
    """

    operation: str
    """``shutdown`` or ``initialize``, for failure messages."""

    duration: float
    """Wall-clock seconds the call took to return, or to be given up on."""

    raised: BaseException | None = None
    """The exception the call raised, if any."""


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
    provider: FeatureProvider | None = None
    """The provider under test, for the steps that call it directly.

    Everything else reaches the provider through :attr:`client`, which is how
    an application would. The lifecycle and metadata steps are the exception:
    they ask the provider itself, because what they verify is the provider's
    own ``shutdown``, ``initialize`` and ``get_metadata`` rather than the SDK's
    handling of them.
    """
    provider_name: str | None = None
    """What the provider called itself through its own metadata.

    Observed rather than configured, because it is what the conformance report
    identifies the provider by: ``TckConfig.name`` is chosen to read well in a
    failure message, which makes it the *configuration* rather than the provider.
    """
    flag_key: str | None = None
    flag_type: FlagType | None = None
    default_value: typing.Any = None
    evaluation_context: EvaluationContext | None = None
    """The context the scenario supplies to the evaluation, if it supplies one.

    ``None`` rather than an empty context, and the distinction is load-bearing:
    one of the ``@targeting`` scenarios is specifically about a rule that cannot
    match because no context was given at all, and a provider that would fall
    over on an empty context rather than on an absent one is exactly what it is
    looking for. So an unset context is passed to the SDK as ``None``, which is
    what an application calling the two-argument form sends.
    """
    last: EvaluationRecord | None = None
    lifecycle: list[LifecycleRecord] = field(default_factory=list)
    """Every direct lifecycle call this scenario made, in order."""
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

    def require_provider(self) -> FeatureProvider:
        if self.provider is None:
            msg = (
                "no provider has been registered in this scenario: a "
                '"Given a stable provider" or "Given a unavailable provider" step '
                "must come first"
            )
            raise AssertionError(msg)
        return self.provider

    def require_shutdown(self) -> LifecycleRecord:
        """The most recent direct ``shutdown`` call, for the steps that bound it."""
        for record in reversed(self.lifecycle):
            if record.operation == "shutdown":
                return record
        msg = (
            "the provider has not been shut down in this scenario: a "
            '"When the provider is shut down" step must come first'
        )
        raise AssertionError(msg)

    def raised(self) -> list[tuple[str, BaseException]]:
        """Every call into the provider that raised, as (what was called, exception).

        The evaluation and the lifecycle calls are recorded separately, since
        they carry different things, but "did anything the scenario asked of
        the provider raise" is one question and this is where it is answered.
        """
        raised: list[tuple[str, BaseException]] = [
            (record.operation, record.raised)
            for record in self.lifecycle
            if record.raised is not None
        ]
        if self.last is not None and self.last.raised is not None:
            raised.append(("the evaluation", self.last.raised))
        return raised

    def has_called_provider(self) -> bool:
        """Whether the scenario has asked anything of the provider yet."""
        return self.last is not None or bool(self.lifecycle)

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
