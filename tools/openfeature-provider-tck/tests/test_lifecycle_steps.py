"""The steps that talk to the provider directly, pinned outside the Gherkin.

The shutdown scenarios live in ``lifecycle.feature``, which is gated on
``@lifecycle``, and neither in-memory self-test declares that -- there is no
backend to reach, so the readiness scenario would pass without testing anything.
That leaves the shutdown, re-initialise and shutdown-bound steps with no
canonical scenario running them here, and a step that first runs in a
containerised adopter's suite fails there looking like a provider defect.

So they are driven directly, with a provider that records what was called of it
and can be told to misbehave. What is pinned is the contract the feature file
relies on: that the calls reach the provider's *own* methods rather than the
SDK's, that a raise is recorded and surfaces through the one "no exception"
step rather than through a second mechanism, that the client still reaches the
instance after it was brought back, and that the scenario's teardown copes with
a provider that was shut down underneath it.
"""

from __future__ import annotations

import typing
from collections.abc import Iterator

import pytest

from openfeature import api
from openfeature.contrib.tools.provider_tck import (
    Capability,
    TckConfig,
    TckState,
    canonical_flag_set,
)
from openfeature.contrib.tools.provider_tck.steps.flag_steps import (
    a_flag_with_key_and_default,
    no_exception_should_have_been_thrown,
    the_flag_was_evaluated_with_details,
    the_resolved_value_should_be,
)
from openfeature.contrib.tools.provider_tck.steps.provider_steps import (
    a_stable_provider,
    the_provider_is_initialized_again,
    the_provider_is_shut_down,
    the_provider_metadata_name_should_not_be_empty,
    the_shutdown_should_have_completed_within,
)
from openfeature.evaluation_context import EvaluationContext
from openfeature.provider import Metadata
from openfeature.provider.in_memory_provider import InMemoryProvider


class RecordingProvider(InMemoryProvider):
    """The SDK's in-memory provider, remembering its lifecycle calls.

    ``fail_shutdown`` and ``fail_initialize`` make the corresponding call raise,
    which is how the recording half of the steps is checked; ``metadata_name``
    is what the metadata step is checked against.
    """

    def __init__(self) -> None:
        super().__init__(canonical_flag_set())
        self.calls: list[str] = []
        self.fail_shutdown = False
        self.fail_initialize = False
        self.metadata_name: typing.Any = "recording"

    def initialize(self, evaluation_context: EvaluationContext) -> None:
        self.calls.append("initialize")
        if self.fail_initialize:
            msg = "initialize refused"
            raise RuntimeError(msg)

    def shutdown(self) -> None:
        self.calls.append("shutdown")
        if self.fail_shutdown:
            msg = "already closed"
            raise RuntimeError(msg)

    def get_metadata(self) -> Metadata:
        return Metadata(name=self.metadata_name)


class _NoControl:
    @property
    def description(self) -> str:
        return "nothing"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...


@pytest.fixture
def provider() -> RecordingProvider:
    return RecordingProvider()


@pytest.fixture
def state(provider: RecordingProvider) -> Iterator[TckState]:
    """A scenario's state, with the recording provider registered by the real step.

    Through ``a_stable_provider`` rather than by hand, so what is tested is the
    hand-off the feature files rely on: the step that registers the provider is
    the one that makes it available to the steps that call it directly.
    """
    config = TckConfig(
        name="lifecycle-steps",
        control=_NoControl(),
        new_provider=lambda: provider,
        capabilities={Capability.EVENTS},
    )
    state = TckState(config=config)
    a_stable_provider(state)
    yield state
    state.teardown()
    api.shutdown()
    api.clear_providers()


# -- the calls reach the provider itself -------------------------------------


def test_shutdown_calls_the_providers_own_shutdown_each_time(
    state: TckState, provider: RecordingProvider
) -> None:
    """Twice asked, twice called -- which the SDK would never do on its own.

    The registry shuts a provider down once per registration. The double-close
    scenario needs two calls on one instance, and gets them only because the
    step bypasses the registry.
    """
    before = list(provider.calls)
    the_provider_is_shut_down(state)
    the_provider_is_shut_down(state)
    assert provider.calls[len(before) :] == ["shutdown", "shutdown"]
    assert [record.operation for record in state.lifecycle] == ["shutdown", "shutdown"]
    no_exception_should_have_been_thrown(state)


def test_initialize_again_reaches_the_same_instance_the_client_uses(
    state: TckState, provider: RecordingProvider
) -> None:
    """The scenario's whole point: after the round trip, the client serves flags
    from the very object that was shut down and brought back.
    """
    the_provider_is_shut_down(state)
    the_provider_is_initialized_again(state)
    assert provider.calls[-2:] == ["shutdown", "initialize"]

    a_flag_with_key_and_default(state, "Boolean", "boolean-flag", "false")
    the_flag_was_evaluated_with_details(state)
    the_resolved_value_should_be(state, "true")
    no_exception_should_have_been_thrown(state)
    assert state.client is not None
    assert state.client.get_provider_status().value == "READY"


def test_initialize_again_passes_an_empty_context(
    state: TckState, provider: RecordingProvider
) -> None:
    seen: list[EvaluationContext] = []
    original = provider.initialize

    def spy(evaluation_context: EvaluationContext) -> None:
        seen.append(evaluation_context)
        original(evaluation_context)

    provider.initialize = spy  # type: ignore[method-assign]
    the_provider_is_initialized_again(state)
    assert len(seen) == 1
    assert seen[0].attributes == {}
    assert seen[0].targeting_key is None


# -- a raise is recorded, and surfaces through the one step ------------------


def test_a_raising_shutdown_fails_the_no_exception_step(
    state: TckState, provider: RecordingProvider
) -> None:
    """Recorded, not propagated: the step returns and the assertion is elsewhere."""
    provider.fail_shutdown = True
    the_provider_is_shut_down(state)

    assert state.lifecycle[-1].raised is not None
    with pytest.raises(AssertionError, match="shutdown raised RuntimeError"):
        no_exception_should_have_been_thrown(state)


def test_a_raising_initialize_fails_the_no_exception_step(
    state: TckState, provider: RecordingProvider
) -> None:
    provider.fail_initialize = True
    the_provider_is_shut_down(state)
    the_provider_is_initialized_again(state)

    with pytest.raises(AssertionError, match="initialize raised RuntimeError"):
        no_exception_should_have_been_thrown(state)


def test_a_lifecycle_raise_is_reported_even_after_a_clean_evaluation(
    state: TckState, provider: RecordingProvider
) -> None:
    """One mechanism for both kinds of call.

    The re-initialise scenario ends with an evaluation and then the no-exception
    step. A raise from the shutdown before it must not be hidden behind the
    evaluation that went fine.
    """
    provider.fail_shutdown = True
    the_provider_is_shut_down(state)
    provider.fail_initialize = False
    the_provider_is_initialized_again(state)
    a_flag_with_key_and_default(state, "Boolean", "boolean-flag", "false")
    the_flag_was_evaluated_with_details(state)

    assert state.last is not None and state.last.raised is None
    with pytest.raises(AssertionError, match="shutdown raised"):
        no_exception_should_have_been_thrown(state)


def test_the_no_exception_step_needs_something_to_have_been_called(
    state: TckState,
) -> None:
    """Before anything was asked of the provider the step has nothing to assert,
    and says so rather than passing on an empty record."""
    with pytest.raises(AssertionError, match="nothing has been asked of the provider"):
        no_exception_should_have_been_thrown(state)


# -- the shutdown bound ------------------------------------------------------


def test_the_shutdown_bound_reads_the_most_recent_shutdown(state: TckState) -> None:
    the_provider_is_shut_down(state)
    the_shutdown_should_have_completed_within(state, "10000")

    state.lifecycle[-1].duration = 11.0
    with pytest.raises(AssertionError, match="shutdown took 11000ms"):
        the_shutdown_should_have_completed_within(state, "10000")


def test_the_shutdown_bound_needs_a_shutdown(state: TckState) -> None:
    with pytest.raises(AssertionError, match="has not been shut down"):
        the_shutdown_should_have_completed_within(state, "10000")


# -- metadata ----------------------------------------------------------------


def test_the_metadata_step_accepts_a_name_and_refuses_an_empty_one(
    state: TckState, provider: RecordingProvider
) -> None:
    the_provider_metadata_name_should_not_be_empty(state)

    for empty in ("", "   ", None):
        provider.metadata_name = empty
        with pytest.raises(AssertionError, match="expected a non-empty string"):
            the_provider_metadata_name_should_not_be_empty(state)


# -- the scenario after this one ---------------------------------------------


def test_a_shut_down_provider_does_not_break_the_next_registration(
    state: TckState, provider: RecordingProvider
) -> None:
    """What the fixture teardown and the next "Given a stable provider" do.

    Both shut the provider down again through the SDK. Requirement 2.5.3 makes
    the second call harmless, and the suite relies on that: a provider that was
    shut down directly is still the registered one when the scenario ends.
    """
    the_provider_is_shut_down(state)

    replacement = RecordingProvider()
    api.set_provider(replacement, state.config.domain)
    assert state.client is not None
    assert state.client.get_boolean_details("boolean-flag", False).value is True
