"""Steps that put a provider under test."""

from __future__ import annotations

import concurrent.futures
import contextlib

from pytest_bdd import given, parsers

from openfeature import api
from openfeature.provider import FeatureProvider

from ..state import TckState

__all__ = ["a_stable_provider", "an_unavailable_provider"]


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
        _set_provider_within(provider, config.domain, config.ready_timeout)
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

    tck_state.client = api.get_client(config.domain)


def _set_provider_within(
    provider: FeatureProvider, domain: str, timeout: float
) -> None:
    """Register a provider, giving up if initialisation has not returned in time.

    ``api.set_provider`` initialises synchronously and has no timeout of its own, so a
    provider that hangs while connecting would hang the whole session with no useful
    message. Running it on a worker thread bounds it.

    The worker is deliberately not cancelled on timeout -- Python cannot interrupt a
    thread blocked in a socket call -- so it is left to finish or die with the process.
    That is acceptable here because a timeout already means the scenario is failing.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(api.set_provider, provider, domain)
        try:
            future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError from None
        finally:
            # Do not block __exit__ on a worker that is still stuck.
            pool.shutdown(wait=False)
