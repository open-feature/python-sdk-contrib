"""Things the Gherkin cannot assert about itself.

Each of these is a way the in-process control path could look correct while
quietly making the conformance suites meaningless.
"""

from __future__ import annotations

import pytest

from openfeature.contrib.tools.provider_tck import (
    CHANGING_FLAG_KEY,
    ConnectionControl,
    ControllableInMemoryProvider,
    InProcessControl,
    canonical_flag_set,
)
from openfeature.event import ProviderEvent


def _resolve_changing(provider: ControllableInMemoryProvider) -> str:
    return provider.resolve_string_details(CHANGING_FLAG_KEY, "unset").value


def test_change_flag_actually_changes_the_resolved_value() -> None:
    """The assumption every configuration-change scenario rests on.

    If ``change_flag`` emitted an event without altering what the provider
    resolves, the scenario would still pass its event assertion and the suite
    would be certifying a signal with nothing behind it.
    """
    control = InProcessControl()
    provider = control.new_provider()
    assert isinstance(provider, ControllableInMemoryProvider)

    before = _resolve_changing(provider)
    control.change_flag()
    after = _resolve_changing(provider)

    assert before != after, "change_flag did not change the resolved value"


def test_change_flag_emits_a_configuration_change_event_naming_the_flag() -> None:
    """The event the scenarios await is the provider's own, and it names the flag."""
    control = InProcessControl()
    provider = control.new_provider()

    seen: list[tuple[ProviderEvent, list[str] | None]] = []

    def record(_provider: object, event: ProviderEvent, details: object) -> None:
        seen.append((event, getattr(details, "flags_changed", None)))

    # attach() is how the SDK registry wires a provider's emitter; doing it by
    # hand keeps this a unit test of the provider rather than of the registry.
    provider.attach(record)
    control.change_flag()

    assert seen, "no event was emitted"
    event, flags_changed = seen[-1]
    assert event is ProviderEvent.PROVIDER_CONFIGURATION_CHANGED
    assert flags_changed == [CHANGING_FLAG_KEY]


def test_change_does_not_leak_into_the_next_scenario() -> None:
    """Scenario isolation.

    A leak here would make the suite order-dependent: a scenario running after
    the configuration-change one would start with ``changing-flag`` already
    flipped, and the failure would look like a provider defect.
    """
    control = InProcessControl()

    first = control.new_provider()
    assert isinstance(first, ControllableInMemoryProvider)
    baseline = _resolve_changing(first)

    control.change_flag()
    assert _resolve_changing(first) != baseline, (
        "precondition: change_flag had no effect"
    )

    control.prepare_scenario()

    second = control.new_provider()
    assert isinstance(second, ControllableInMemoryProvider)
    assert _resolve_changing(second) == baseline, (
        "the next scenario did not start from the baseline"
    )


def test_change_flag_without_a_provider_fails_clearly() -> None:
    """In-process the flag store and the provider are the same object, so there is
    nothing to change before one exists. Saying so beats an AttributeError."""
    control = InProcessControl()
    with pytest.raises(RuntimeError, match="must create one"):
        control.change_flag()


def test_in_process_control_does_not_pretend_to_have_a_connection() -> None:
    """The load-bearing one.

    A no-op ``disconnect`` would report the ``@stale`` scenarios as passed
    against a provider that cannot go stale -- precisely the silent-green
    failure a conformance suite must never have. ``InProcessControl`` therefore
    does not implement ``ConnectionControl`` at all, and the TCK turns that into
    a skip with a reason.
    """
    assert not isinstance(InProcessControl(), ConnectionControl), (
        "InProcessControl implements ConnectionControl: an in-memory provider has no "
        "connection to lose, and a no-op implementation would make the @stale "
        "scenarios pass without testing anything"
    )


def test_canonical_flag_set_omits_missing_flag() -> None:
    """The property the FLAG_NOT_FOUND scenario depends on.

    Seeding ``missing-flag`` would turn that scenario green for the wrong
    reason, and nothing else in the suite would notice.
    """
    assert "missing-flag" not in canonical_flag_set()


def test_update_flags_names_the_union_of_old_and_new_keys() -> None:
    """Appendix A asks for the union, not just the new keys.

    A consumer caching evaluations needs to know everything that might have
    changed, and a key that disappeared has changed as much as one that arrived.
    """
    provider = ControllableInMemoryProvider(canonical_flag_set())

    seen: list[list[str] | None] = []
    provider.attach(lambda _p, _e, details: seen.append(details.flags_changed))

    provider.update_flags({})

    assert seen, "no event was emitted"
    assert seen[-1] is not None
    assert set(seen[-1]) == set(canonical_flag_set()), (
        "the event did not name every flag that disappeared"
    )
