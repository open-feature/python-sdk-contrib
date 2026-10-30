"""What the event assertions read, and what they leave behind.

Both halves matter to a chain like stale, then error, then ready: each assertion
has to see the records an earlier one did not claim, or an ordering question is
answered from an emptied log. No canonical scenario asks an ordering question
yet, so the step is driven directly here.

The events are recorded by hand rather than provoked out of a provider. What is
under test is the bookkeeping -- which record an await claims, and which it
leaves -- and a real provider cannot be made to emit an error before a ready on
demand.
"""

from __future__ import annotations

import typing

import pytest

from openfeature.client import OpenFeatureClient
from openfeature.contrib.tools.tck import (
    BackendType,
    Capability,
    ControllableInMemoryProvider,
    TckConfig,
    TckState,
    canonical_flag_set,
)
from openfeature.contrib.tools.tck.state import EventRecorder
from openfeature.contrib.tools.tck.steps.event_steps import (
    an_event_was_fired,
    the_event_handler_should_have_been_executed,
    the_event_handler_should_have_been_executed_with_none_before,
    the_event_handler_should_have_been_executed_within,
)
from openfeature.event import EventDetails, EventHandler, ProviderEvent

_BY_KIND = {
    "ready": ProviderEvent.PROVIDER_READY,
    "stale": ProviderEvent.PROVIDER_STALE,
    "error": ProviderEvent.PROVIDER_ERROR,
    "change": ProviderEvent.PROVIDER_CONFIGURATION_CHANGED,
}


class _NoControl:
    @property
    def description(self) -> str:
        return "nothing"

    @property
    def backend_type(self) -> BackendType:
        return "in-process"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...


class _SilentClient:
    """A client that accepts handlers and never calls one.

    The SDK replays a matching event the moment a handler is attached to an
    already-ready provider, which is a feature everywhere except here: it would
    put a record in the log beside the ones each test is about.
    """

    def __init__(self) -> None:
        self.attached: list[ProviderEvent] = []

    def add_handler(self, event: ProviderEvent, handler: EventHandler) -> None:
        self.attached.append(event)

    def remove_handler(self, event: ProviderEvent, handler: EventHandler) -> None:
        self.attached.remove(event)


@pytest.fixture
def state() -> TckState:
    """A scenario's state with a handler for every kind, and no events recorded.

    Every kind, because the ordering step requires the forbidden kind's handler
    too, and a test that had to remember to register it would be testing its own
    setup.
    """
    config = TckConfig(
        name="event-order-steps",
        control=_NoControl(),
        new_provider=lambda: ControllableInMemoryProvider(canonical_flag_set()),
        capabilities={Capability.EVENTS},
        event_timeout=0.2,
    )
    state = TckState(config=config)
    client = typing.cast("OpenFeatureClient", _SilentClient())
    for event in _BY_KIND.values():
        state.recorders[event] = EventRecorder(client, event, state.events)
    return state


def _fire(state: TckState, *kinds: str) -> None:
    """Record one event of each kind named, in that order."""
    for kind in kinds:
        state.events.record(_BY_KIND[kind], EventDetails())


# -- the ordering assertion ---------------------------------------------------


def test_an_event_of_the_forbidden_kind_recorded_first_fails_the_ordering(
    state: TckState,
) -> None:
    """The error was recorded before the ready, which is what a scenario forbids."""
    _fire(state, "error", "ready")

    with pytest.raises(AssertionError, match="error event was recorded before"):
        the_event_handler_should_have_been_executed_with_none_before(
            state, "ready", "error"
        )


def test_the_same_records_in_the_other_order_pass(state: TckState) -> None:
    """And the ready is claimed, while the error is left for whatever asks next."""
    _fire(state, "ready", "error")

    the_event_handler_should_have_been_executed_with_none_before(
        state, "ready", "error"
    )

    recorder = state.recorders[ProviderEvent.PROVIDER_READY]
    assert recorder.last is not None
    the_event_handler_should_have_been_executed(state, "error")


def test_an_ordering_question_with_nothing_recorded_times_out(state: TckState) -> None:
    """It awaits the event it is about: an absence is a failure, not a silent pass.

    Which is the whole reason this step replaced one asking whether an event had
    *not* been executed. That one passes the instant it is reached.
    """
    with pytest.raises(AssertionError, match="waiting for a PROVIDER_READY event"):
        the_event_handler_should_have_been_executed_with_none_before(
            state, "ready", "error"
        )


def test_the_forbidden_kind_needs_a_handler_of_its_own(state: TckState) -> None:
    """Without one nothing of that kind is ever recorded, so the assertion would
    hold for a provider that fired it loudly."""
    del state.recorders[ProviderEvent.PROVIDER_ERROR]
    _fire(state, "error", "ready")

    with pytest.raises(AssertionError, match="no handler was registered"):
        the_event_handler_should_have_been_executed_with_none_before(
            state, "ready", "error"
        )


def test_a_failed_ordering_leaves_the_record_it_is_about(state: TckState) -> None:
    """A failure consumes nothing: the step that reports it did not get its answer."""
    _fire(state, "error", "ready")

    with pytest.raises(AssertionError):
        the_event_handler_should_have_been_executed_with_none_before(
            state, "ready", "error"
        )

    the_event_handler_should_have_been_executed(state, "ready")


# -- what an await leaves behind ---------------------------------------------


def test_awaiting_one_kind_does_not_throw_away_another_kinds_record(
    state: TckState,
) -> None:
    """The semantic the ordering step rests on.

    An await that drained the log up to its match would discard the error that
    arrived first, and the ordering question that follows would find nothing
    left to object to.
    """
    _fire(state, "error", "change", "ready")

    the_event_handler_should_have_been_executed(state, "change")

    with pytest.raises(AssertionError, match="error event was recorded before"):
        the_event_handler_should_have_been_executed_with_none_before(
            state, "ready", "error"
        )


def test_an_await_claims_one_record_rather_than_every_one_of_its_kind(
    state: TckState,
) -> None:
    """A chain cannot satisfy two awaits with one event.

    The stale scenario depends on it: it consumes the initial ready and asserts a
    second, distinct one once the backend is back.
    """
    _fire(state, "ready")

    the_event_handler_should_have_been_executed(state, "ready")

    with pytest.raises(AssertionError, match="waiting for a PROVIDER_READY event"):
        the_event_handler_should_have_been_executed_within(state, "ready", "150")


def test_a_consumed_record_is_not_evidence_for_a_later_ordering(
    state: TckState,
) -> None:
    """What "before it" means: before it, among what no step has claimed.

    An error a scenario already awaited was that step's answer. Reading it again
    as evidence would make every later ordering assertion fail over an event the
    scenario asked for on purpose.
    """
    _fire(state, "error", "ready")
    an_event_was_fired(state, "error")

    the_event_handler_should_have_been_executed_with_none_before(
        state, "ready", "error"
    )
