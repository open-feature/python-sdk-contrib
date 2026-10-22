"""Per-scenario state: what a scenario accumulates, and how it observes events.

Separate from :mod:`plugin` so the step modules can import these types at the top
level. The step modules are loaded by the plugin as plugins in their own right,
and a step importing from the plugin module that loads it reads like a cycle even
where it is not one.
"""

from __future__ import annotations

import threading
import time
import typing
from dataclasses import dataclass, field

from openfeature.client import OpenFeatureClient
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import EventDetails, ProviderEvent
from openfeature.flag_evaluation import FlagMetadata, FlagType
from openfeature.provider import FeatureProvider

from .config import TckConfig

__all__ = [
    "EvaluationRecord",
    "EventLog",
    "EventRecorder",
    "LifecycleRecord",
    "ProviderEventRecord",
    "TckState",
]


@dataclass
class EvaluationRecord:
    """The outcome of one flag evaluation, flattened across the five typed calls."""

    value: typing.Any = None
    variant: str | None = None
    reason: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    flag_metadata: FlagMetadata | None = None
    """The metadata the provider attached to the resolution, if the call returned.

    ``None`` means no evaluation got as far as returning details, which is a
    different answer from an empty map and is why the metadata assertions refuse
    it rather than reading it as empty.
    """
    raised: BaseException | None = None
    """The exception the call raised, if any.

    In Python an errored evaluation returns the code default in the details
    rather than raising, so this stays ``None`` on the error paths the suite
    exercises. It is what "no exception should have been thrown" asserts.
    """


@dataclass
class LifecycleRecord:
    """The outcome of one direct call into the provider's lifecycle.

    Recorded the same way an evaluation is -- what it raised, if anything -- so
    that "no exception should have been thrown" reads one kind of record for
    both, plus how long it took, which is what the prompt-shutdown scenario
    bounds.
    """

    operation: str
    """``shutdown`` or ``initialize``, for failure messages."""

    duration: float
    """Wall-clock seconds the call took to return, or to be given up on."""

    raised: BaseException | None = None
    """The exception the call raised, if any."""


@dataclass(frozen=True)
class ProviderEventRecord:
    """One provider event a scenario's handlers observed."""

    event: ProviderEvent
    """Which kind of event it was, which is what an await matches on."""

    details: EventDetails
    """What the SDK handed the handler."""

    sequence: int
    """Arrival order across every kind.

    Not derivable from a per-kind queue, and an ordering question needs it: "a
    ready event, and no error before it" is a relation between two kinds, and two
    independent queues record no relation at all.
    """


class EventLog:
    """Every provider event the scenario's handlers saw, in arrival order.

    One log rather than a queue per kind, because of what a scenario asks of it.
    Awaiting is still per kind -- a scenario consumes ready events one at a time
    without touching the errors -- but an ordering assertion spans kinds, and
    there is nowhere else for the order to be.

    **A claim takes the one record it matched and leaves every other**, records
    of other kinds included, which is the half that is easy to get wrong.
    Draining up to the match would discard an error recorded before an awaited
    ready, and the scenario asking whether one came first would find nothing left
    to object to.

    A condition rather than a :class:`queue.Queue`: a provider with a background
    thread records from that thread while the scenario waits on the main one, and
    a claim has to pick its own kind out of the middle of the log rather than take
    whatever is at the head.
    """

    def __init__(self) -> None:
        self._arrived = threading.Condition()
        self._records: list[ProviderEventRecord] = []
        self._recorded = 0

    def record(self, event: ProviderEvent, details: EventDetails) -> None:
        """Append what a handler was just given, and wake whoever is waiting."""
        with self._arrived:
            self._recorded += 1
            self._records.append(
                ProviderEventRecord(
                    event=event, details=details, sequence=self._recorded
                )
            )
            self._arrived.notify_all()

    def wait_for(
        self, event: ProviderEvent, timeout: float
    ) -> ProviderEventRecord | None:
        """The oldest unclaimed record of ``event``, waiting up to ``timeout`` for one.

        The record stays in the log, so a caller that has an ordering question
        can still ask it; :meth:`claim` is what takes the record out. ``None``
        if none arrived in time.
        """
        deadline = time.monotonic() + timeout
        with self._arrived:
            while True:
                for record in self._records:
                    if record.event is event:
                        return record
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._arrived.wait(remaining)

    def kinds_before(self, record: ProviderEventRecord) -> list[ProviderEvent]:
        """The kinds of the unclaimed records that arrived ahead of ``record``.

        Unclaimed, because a record an earlier step consumed was that step's
        answer and is not this one's evidence -- the same reading Java's suite
        takes of the list it removes from.
        """
        with self._arrived:
            return [
                earlier.event
                for earlier in self._records
                if earlier.sequence < record.sequence
            ]

    def claim(self, record: ProviderEventRecord) -> None:
        """Take this one record out of the log, leaving every other in place."""
        with self._arrived:
            self._records = [
                kept for kept in self._records if kept.sequence != record.sequence
            ]


class EventRecorder:
    """Captures the events of one type, in order, so a scenario consumes them one at a time.

    Consuming rather than merely observing is what makes the stale scenario
    work: it awaits a ``PROVIDER_READY`` at the start and a second, different
    one once the backend is back, and a recorder that only remembered "ready has
    fired at some point" would report the second assertion as satisfied by the
    first event.

    What it consumes from is the scenario's one :class:`EventLog`, shared with
    every other recorder, so the order the kinds arrived in survives a consumed
    event.
    """

    def __init__(
        self, client: OpenFeatureClient, event: ProviderEvent, log: EventLog
    ) -> None:
        self.event = event
        self._client = client
        self._log = log
        self.last: EventDetails | None = None

        # The SDK replays a matching event on registration when the provider is
        # already in the corresponding state, which is what lets the feature
        # files register handlers after "Given a stable provider" without racing.
        client.add_handler(event, self._on_event)

    def _on_event(self, details: EventDetails) -> None:
        self._log.record(self.event, details)

    def await_event(self, timeout: float) -> EventDetails:
        """Consume the next event of this recorder's type."""
        record = self.await_record(timeout)
        self.claim(record)
        return record.details

    def await_record(self, timeout: float) -> ProviderEventRecord:
        """Wait for the next unclaimed event of this type, leaving it in the log.

        Separate from :meth:`await_event` for the ordering assertion, which has
        to read what was recorded ahead of the event *before* consuming it: a
        claim is what makes "ahead of it" unanswerable.
        """
        record = self._log.wait_for(self.event, timeout)
        if record is None:
            msg = (
                f"timed out after {timeout}s waiting for a {self.event.value} event. "
                f"If the provider is simply slower than this to notice, raise "
                f"TckConfig.event_timeout rather than treating it as a failure"
            )
            raise AssertionError(msg)
        return record

    def claim(self, record: ProviderEventRecord) -> None:
        """Consume a record this recorder awaited, and remember it as the last seen."""
        self._log.claim(record)
        self.last = record.details

    def detach(self) -> None:
        self._client.remove_handler(self.event, self._on_event)


@dataclass
class TckState:
    """Everything one scenario accumulates."""

    config: TckConfig
    client: OpenFeatureClient | None = None
    provider: FeatureProvider | None = None
    """The provider under test, for the steps that call it directly.

    Everything else reaches the provider through :attr:`client`, as an
    application would. The lifecycle and metadata steps are the exception: what
    they verify is the provider's own ``shutdown``, ``initialize`` and
    ``get_metadata`` rather than the SDK's handling of them.
    """
    flag_key: str | None = None
    flag_type: FlagType | None = None
    default_value: typing.Any = None
    evaluation_context: EvaluationContext | None = None
    """The context the scenario supplies to the evaluation, if it supplies one.

    ``None`` rather than an empty context, and the distinction is load-bearing:
    one of the ``@targeting`` scenarios is about a rule that cannot match because
    no context was given at all. So an unset context is passed to the SDK as
    ``None``, which is what an application calling the two-argument form sends.
    """
    last: EvaluationRecord | None = None
    lifecycle: list[LifecycleRecord] = field(default_factory=list)
    """Every direct lifecycle call this scenario made, in order."""
    remembered: typing.Any = None
    has_memory: bool = False
    recorders: dict[ProviderEvent, EventRecorder] = field(default_factory=dict)
    events: EventLog = field(default_factory=EventLog)
    """Every event the scenario's recorders saw, in one order across the kinds.

    Shared by every recorder rather than owned by one, because that order is the
    only thing an ordering assertion can read.
    """

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
