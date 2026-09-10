"""Run the conformance suite against the SDK's own in-memory provider.

This is the TCK's self-test, and it earns its keep twice over.

It is the **reference adoption** for a provider with no backend. Everything a
file-based or environment-variable provider has to write is here: one fixture
and one call.

It is also the **Docker-free canary**. Needing no container and no network, it
runs in a fraction of a second, which makes it the fast check that catches a
broken step definition, a mis-wired capability gate or a regression in the
shared harness long before a containerised suite would.

What it does not do is license providers that have a backend to test themselves
this way -- see ``BackendControl`` for why.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.provider_tck import (
    Capability,
    KnownDeviation,
    TckConfig,
    canonical_flag_set,
    features_path,
)
from openfeature.provider import FeatureProvider
from openfeature.provider.in_memory_provider import InMemoryProvider


class PlainMemoryControl:
    """Backend control for the SDK's stock in-memory provider.

    ``prepare_scenario`` is a no-op because the provider is rebuilt from the
    canonical flag set for every scenario, so each one already starts from an
    untouched baseline.

    ``change_flag`` cannot be implemented at all, and the error says why.
    Appendix A of the specification requires an SDK's in-memory provider to
    "support a means of updating the flag set, resulting in the emission of
    PROVIDER_CONFIGURATION_CHANGED events"; the Python SDK's copies its mapping
    in the constructor and exposes no way to change it. The suite below
    therefore leaves ``CONFIGURATION_CHANGE`` undeclared and the scenario is
    reported as skipped with its reason, which is the honest outcome. Reaching
    this error would mean the capability had been declared anyway.
    """

    @property
    def description(self) -> str:
        return "the Python SDK's InMemoryProvider, rebuilt per scenario"

    def prepare_scenario(self) -> None:
        return None

    def change_flag(self) -> None:
        msg = (
            "openfeature.provider.in_memory_provider.InMemoryProvider cannot change its "
            "flag set: it copies the mapping in its constructor and exposes no update "
            "method, so a configuration change can be neither applied nor signalled. "
            "Appendix A of the specification requires it. See "
            "ControllableInMemoryProvider for what the SDK's provider is missing"
        )
        raise NotImplementedError(msg)


def _new_provider() -> FeatureProvider:
    return InMemoryProvider(canonical_flag_set())


@pytest.fixture(scope="session")
def tck_config(tck_known_deviations: tuple[KnownDeviation, ...]) -> TckConfig:
    """Declare the provider under test and what it can do.

    Each omission is a fact about the provider rather than a convenience:

    * ``CONFIGURATION_CHANGE`` -- omitted because the SDK's in-memory provider
      cannot update its flag set. That is a finding, not a configuration choice;
      see ``PlainMemoryControl``.
    * ``STALE`` and ``UNAVAILABLE_INIT`` -- omitted because there is no
      connection to lose. ``PlainMemoryControl`` does not implement
      ``ConnectionControl`` for the same reason, and the two omissions keep each
      other honest: the scenarios are skipped before any step can reach an
      operation the control cannot perform.
    * ``TARGETING`` and ``CACHING`` -- omitted because no scenario carries their
      tags yet, so leaving them out skips nothing.
    * ``LIFECYCLE`` -- omitted because there is no backend to reach. The
      capability asserts that initialisation actually contacts a backend and
      that the outcome is observable; this provider's ``initialize`` is a no-op
      and the SDK dispatches ``PROVIDER_READY`` around it regardless, so the
      readiness scenario would pass here without testing anything. It passed
      vacuously while the feature was gated on ``EVENTS``, which is precisely
      the failure mode the split of ``@lifecycle`` from ``@events`` exists to
      end. A skip with a reason is the honest outcome.

    ``known_deviations`` is the one thing here that is not a claim about what
    this provider supports: it is the acknowledgement of a scenario the SDK
    fails, which the results payload still reports as a failure. See
    ``conftest.py``.
    """
    return TckConfig(
        name="in-memory",
        control=PlainMemoryControl(),
        new_provider=_new_provider,
        capabilities={
            Capability.EVENTS,
            Capability.OBJECT,
            Capability.NUMERIC_COERCION,
        },
        known_deviations=tck_known_deviations,
    )


scenarios(features_path())
