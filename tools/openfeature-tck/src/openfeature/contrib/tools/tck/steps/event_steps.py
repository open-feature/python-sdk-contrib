"""Steps covering provider events, connection loss and client status."""

from __future__ import annotations

from pytest_bdd import given, parsers, then, when

from openfeature.event import ProviderEvent
from openfeature.provider import ProviderStatus

from ..control import ConnectionControl, unsupported_control
from ..state import EventRecorder, TckState

__all__ = [
    "an_event_handler",
    "an_event_was_fired",
    "the_client_should_be_in_state",
    "the_connection_is_lost",
    "the_connection_is_restored",
    "the_event_handler_should_have_been_executed",
    "the_event_handler_should_have_been_executed_with_none_before",
    "the_event_handler_should_have_been_executed_within",
    "the_flag_should_be_part_of_the_event_payload",
]

_EVENT_KINDS = "ready|stale|error|change"
"""The kinds a step may name, spelled once so two steps cannot drift apart."""

_EVENT_BY_NAME: dict[str, ProviderEvent] = {
    "ready": ProviderEvent.PROVIDER_READY,
    "stale": ProviderEvent.PROVIDER_STALE,
    "error": ProviderEvent.PROVIDER_ERROR,
    "change": ProviderEvent.PROVIDER_CONFIGURATION_CHANGED,
}

_STATUS_BY_NAME: dict[str, ProviderStatus] = {
    "ready": ProviderStatus.READY,
    "stale": ProviderStatus.STALE,
    "error": ProviderStatus.ERROR,
}


def _event(name: str) -> ProviderEvent:
    try:
        return _EVENT_BY_NAME[name]
    except KeyError:
        msg = f"unknown event kind {name!r}"
        raise AssertionError(msg) from None


@given(parsers.re(rf"^an? (?P<kind>{_EVENT_KINDS}) event handler$"))
def an_event_handler(tck_state: TckState, kind: str) -> None:
    """Attach a recorder for one event type.

    Handlers are attached after the provider is registered, and the SDK replays a
    matching event when the provider is already in the corresponding state, so
    "Given a stable provider" followed by "And a ready event handler" is not a
    race.
    """
    event = _event(kind)
    if event in tck_state.recorders:
        return
    client = tck_state.require_client()
    tck_state.recorders[event] = EventRecorder(client, event, tck_state.events)


@when(parsers.re(rf"^a (?P<kind>{_EVENT_KINDS}) event was fired$"))
def an_event_was_fired(tck_state: TckState, kind: str) -> None:
    """Consume an event, so a later assertion observes the next one rather than this.

    The stale scenario depends on it, consuming the initial ``PROVIDER_READY``
    here and asserting a second, distinct one once the backend is back.
    """
    recorder = tck_state.require_recorder(_event(kind))
    recorder.await_event(tck_state.config.event_timeout)


@then(
    parsers.re(
        rf"^the (?P<kind>{_EVENT_KINDS}) event handler should have been executed$"
    )
)
def the_event_handler_should_have_been_executed(tck_state: TckState, kind: str) -> None:
    recorder = tck_state.require_recorder(_event(kind))
    recorder.await_event(tck_state.config.event_timeout)


@then(
    parsers.re(
        rf"^the (?P<kind>{_EVENT_KINDS}) event handler should have been "
        rf"executed within (?P<millis>\d+)ms$"
    )
)
def the_event_handler_should_have_been_executed_within(
    tck_state: TckState, kind: str, millis: str
) -> None:
    """Bound the wait explicitly.

    The scenarios using this assert promptness, not merely eventual arrival, so
    the bound overrides ``event_timeout`` rather than being clamped by it.
    """
    recorder = tck_state.require_recorder(_event(kind))
    recorder.await_event(int(millis) / 1000.0)


@then(
    parsers.re(
        rf"^the (?P<kind>{_EVENT_KINDS}) event handler should have been executed "
        rf"with no (?P<forbidden>{_EVENT_KINDS}) event before it$"
    )
)
def the_event_handler_should_have_been_executed_with_none_before(
    tck_state: TckState, kind: str, forbidden: str
) -> None:
    """Await one kind of event and assert no event of another kind preceded it.

    This is how a scenario says "and no error": as an **order**, not as a window.
    "No error event fired" can only be answered over some stretch of time, and at
    any instant an event that never fires and one that fires a moment later are
    the same observation -- so a step asking it that way either slows every run
    down or passes because nothing has arrived yet. "No error before the provider
    came back ready" is a question about what was recorded, and the recording
    answers it with no clock involved.

    Both handlers have to be registered, the forbidden kind's included. An
    unregistered kind records nothing, so the assertion would hold for a provider
    that fired it loudly -- the one way this step could go quietly vacuous.
    """
    awaited = _event(kind)
    forbidden_event = _event(forbidden)
    recorder = tck_state.require_recorder(awaited)
    tck_state.require_recorder(forbidden_event)

    record = recorder.await_record(tck_state.config.event_timeout)
    before = tck_state.events.kinds_before(record)
    if forbidden_event in before:
        kinds = ", ".join(earlier.value for earlier in before)
        msg = (
            f"a {forbidden} event was recorded before the {kind} event, which this "
            f"scenario forbids. Recorded first: {kinds}"
        )
        raise AssertionError(msg)

    # Consumed only now the ordering holds, so the record a failure is about is
    # still in the log for whatever reports it.
    recorder.claim(record)


@then("the flag should be part of the event payload")
def the_flag_should_be_part_of_the_event_payload(tck_state: TckState) -> None:
    """Assert the configuration-change event named the flag that changed.

    A consumer caching evaluations needs to know what to invalidate, and an event
    carrying no keys forces it to invalidate everything.
    """
    key, _flag_type, _default = tck_state.require_flag()
    recorder = tck_state.require_recorder(ProviderEvent.PROVIDER_CONFIGURATION_CHANGED)

    if recorder.last is None:
        msg = (
            "no configuration-change event has been consumed in this scenario: a "
            '"the change event handler should have been executed" step must come first'
        )
        raise AssertionError(msg)

    changed = recorder.last.flags_changed or []
    if key in changed:
        return

    if not changed:
        msg = (
            f"the configuration-change event carried no changed flags, expected it to "
            f"name {key!r}"
        )
    else:
        msg = f"the configuration-change event named {changed}, expected it to include {key!r}"
    raise AssertionError(msg)


def _connection_control(tck_state: TckState, operation: str) -> ConnectionControl:
    control = tck_state.config.control
    if not isinstance(control, ConnectionControl):
        raise unsupported_control(control, operation)
    return control


@when("the connection is lost")
def the_connection_is_lost(tck_state: TckState) -> None:
    _connection_control(tck_state, "disconnect").disconnect()


@when("the connection is restored")
def the_connection_is_restored(tck_state: TckState) -> None:
    _connection_control(tck_state, "reconnect").reconnect()


@then(parsers.re(r"^the client should be in (?P<name>ready|stale|error) state$"))
def the_client_should_be_in_state(tck_state: TckState, name: str) -> None:
    """Assert the provider status the client reports.

    No polling: the SDK writes provider status before running handlers, so if the
    event this follows arrived, the status is already current.
    """
    client = tck_state.require_client()
    expected = _STATUS_BY_NAME[name]
    actual = client.get_provider_status()
    if actual != expected:
        msg = f"client reports status {actual}, expected {expected}"
        raise AssertionError(msg)
