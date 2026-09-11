"""Steps that put a provider under test, and the ones that talk to it directly."""

from __future__ import annotations

import concurrent.futures
import contextlib
import time
from collections.abc import Callable

from pytest_bdd import given, parsers, then, when

from openfeature import api
from openfeature.evaluation_context import EvaluationContext

from ..state import LifecycleRecord, TckState

__all__ = [
    "a_stable_provider",
    "an_unavailable_provider",
    "the_provider_is_initialized_again",
    "the_provider_is_shut_down",
    "the_provider_metadata_name_should_not_be_empty",
    "the_shutdown_should_have_completed_within",
]


@given(parsers.re(r"^an? stable provider$"))
def a_stable_provider(tck_state: TckState) -> None:
    """Register the provider under test against the running, seeded backend.

    ``api.set_provider`` initialises synchronously and dispatches
    ``PROVIDER_READY``, so by the time this step returns the provider is ready
    and every scenario that follows can assume it. A suite that started
    evaluating before that would report races in the TCK as defects in the
    provider.
    """
    config = tck_state.config
    provider = config.new_provider()
    if provider is None:
        msg = "TckConfig.new_provider returned None"
        raise AssertionError(msg)

    try:
        _call_within(
            lambda: api.set_provider(provider, config.domain), config.ready_timeout
        )
    except TimeoutError:
        msg = (
            f"the provider did not become ready within {config.ready_timeout}s. The backend "
            f"is up and seeded at this point, so either initialisation is genuinely hanging "
            f"or TckConfig.ready_timeout is too short"
        )
        raise AssertionError(msg) from None
    except Exception as exc:
        msg = (
            f"registering the provider raised {exc!r}. The backend is up and seeded "
            f"at this point, so this is a genuine initialisation failure rather than "
            f"the unavailable-backend case"
        )
        raise AssertionError(msg) from exc

    tck_state.provider = provider
    tck_state.client = api.get_client(config.domain)


@given(parsers.re(r"^an? unavailable provider$"))
def an_unavailable_provider(tck_state: TckState) -> None:
    """Register a provider pointed at a backend that does not exist.

    Neither a failed initialisation nor a raised exception during registration
    is a failure here: what the contract requires is that the provider settles
    into an observable error state promptly, which the scenario asserts through
    the event and the client status. The SDK's registry already converts a
    raising ``initialize`` into ``PROVIDER_ERROR``, so registration itself is
    expected to return normally -- but a provider that raises anyway must not
    take the scenario down with it, which is why this is caught rather than
    propagated.
    """
    config = tck_state.config

    if config.new_unavailable_provider is None:
        msg = (
            "TckConfig.new_unavailable_provider is None but an @unavailable scenario "
            "ran. This is a test-configuration bug rather than a provider defect: the "
            "suite declared Capability.UNAVAILABLE_INIT without supplying a provider "
            "that cannot reach its backend. Remove that capability, or supply the factory"
        )
        raise AssertionError(msg)

    provider = config.new_unavailable_provider()
    if provider is None:
        msg = "TckConfig.new_unavailable_provider returned None"
        raise AssertionError(msg)

    # A raising initialize is already converted to PROVIDER_ERROR by the SDK's
    # registry, so this is belt and braces: a provider that raises anyway must
    # not take the scenario down with it, because the contract is about the
    # observable error state rather than about how registration returned.
    with contextlib.suppress(Exception):
        api.set_provider(provider, config.domain)

    tck_state.provider = provider
    tck_state.client = api.get_client(config.domain)


@when("the provider is shut down")
def the_provider_is_shut_down(tck_state: TckState) -> None:
    """Call the provider's own ``shutdown``, directly.

    Not through the SDK. The SDK shuts a provider down when it is replaced or
    when the API is shut down, but going that way would test the registry's
    bookkeeping as much as the provider, and Appendix B already does that.
    Calling ``shutdown`` on the instance is also what lets a scenario call it
    twice: the registry only ever calls it once per registration.

    The registry is not told. The client still points at the same instance, so
    an evaluation after "the provider is initialized again" reaches the very
    object that was shut down and brought back, which is what that scenario
    asserts. And when the scenario ends the SDK shuts the provider down once
    more on its own -- a second call, which requirement 2.5.3 makes harmless.
    """
    _record_lifecycle_call(tck_state, "shutdown", tck_state.require_provider().shutdown)


@when("the provider is initialized again")
def the_provider_is_initialized_again(tck_state: TckState) -> None:
    """Call the provider's own ``initialize`` after it was shut down.

    With an empty context, as the SDK would with none set. Direct for the same
    reason as the shutdown step: re-registering through the SDK would create a
    new registration around the same instance, and what is under test is that
    the instance itself reverts to an initialisable state.
    """
    provider = tck_state.require_provider()
    _record_lifecycle_call(
        tck_state, "initialize", lambda: provider.initialize(EvaluationContext())
    )


@then(parsers.re(r"^the shutdown should have completed within (?P<millis>\d+)ms$"))
def the_shutdown_should_have_completed_within(tck_state: TckState, millis: str) -> None:
    """Bound the most recent shutdown.

    The scenario using this runs against a backend that will never answer, so
    what it asserts is that shutdown returns rather than waiting for a graceful
    close that cannot happen. A shutdown that was given up on because it
    outlasted ``TckConfig.ready_timeout`` fails here too: its recorded duration
    is however long the suite waited before moving on.
    """
    record = tck_state.require_shutdown()
    bound = int(millis) / 1000.0
    if record.duration > bound:
        msg = (
            f"shutdown took {record.duration * 1000:.0f}ms, expected it to complete within "
            f"{millis}ms. A shutdown that waits on a backend that is gone hangs the host "
            f"application's own shutdown"
        )
        raise AssertionError(msg)


@then("the provider metadata name should not be empty")
def the_provider_metadata_name_should_not_be_empty(tck_state: TckState) -> None:
    """Assert the provider identifies itself (requirement 2.1.1).

    Asked of the provider rather than of ``api.get_provider_metadata``, which
    would answer for whatever the registry holds under the domain: the same
    object here, but the question is about the provider.
    """
    provider = tck_state.require_provider()
    try:
        metadata = provider.get_metadata()
    except Exception as exc:
        msg = f"get_metadata raised {exc!r}: the provider cannot say what it is"
        raise AssertionError(msg) from exc

    name = getattr(metadata, "name", None)
    if not isinstance(name, str) or not name.strip():
        msg = (
            f"the provider metadata name is {name!r}, expected a non-empty string. A "
            f"conformance report keyed on the name cannot be attributed without one"
        )
        raise AssertionError(msg)


def _record_lifecycle_call(
    tck_state: TckState, operation: str, call: Callable[[], object]
) -> None:
    """Make one direct lifecycle call and record how it went, raising nothing.

    An exception is recorded rather than propagated, for the same reason an
    evaluation's is: "no exception should have been thrown" is a step of its
    own, and a scenario that wants a raise to fail says so there. Only
    ``Exception`` is caught, though. The shutdown scenario that matters most is
    the one against a backend that is gone, which is exactly where somebody
    might reach for Ctrl-C, and a ``KeyboardInterrupt`` recorded as "shutdown
    raised" would carry the run on past the thing they interrupted.

    A call that outlasts ``TckConfig.ready_timeout`` is given up on and recorded
    as a ``TimeoutError`` with the time waited, so a hanging shutdown fails its
    scenario with a message rather than hanging the session.
    """
    started = time.perf_counter()
    raised: BaseException | None = None
    try:
        _call_within(call, tck_state.config.ready_timeout)
    except TimeoutError:
        raised = TimeoutError(
            f"{operation} did not return within {tck_state.config.ready_timeout}s"
        )
    except Exception as exc:  # recorded here, asserted on by its own step
        raised = exc
    duration = time.perf_counter() - started
    tck_state.lifecycle.append(
        LifecycleRecord(operation=operation, duration=duration, raised=raised)
    )


def _call_within(call: Callable[[], object], timeout: float) -> None:
    """Make a call into the provider, giving up if it has not returned in time.

    Neither ``api.set_provider`` nor a provider's own ``shutdown`` has a timeout
    of its own, so one that hangs while talking to its backend would hang the
    whole session with no useful message. Running it on a worker thread bounds
    it.

    The worker is deliberately not cancelled on timeout -- Python cannot interrupt a
    thread blocked in a socket call -- so it is left to finish or die with the process.
    That is acceptable here because a timeout already means the scenario is failing.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(call)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError from None
        finally:
            # Do not block __exit__ on a worker that is still stuck.
            pool.shutdown(wait=False)
