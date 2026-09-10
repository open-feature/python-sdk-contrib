"""Run the conformance suite against the TCK's own updatable in-memory provider.

This is the suite that exercises the configuration-change path, and it exists
because the SDK's in-memory provider cannot: it has no way to update a flag set,
so ``test_in_memory_conformance`` necessarily skips those scenarios. Without
this suite the change-event step definitions would ship with no coverage at all,
and a break in them would first surface in a containerised provider suite where
it looks like a provider defect.

It is also the reference for what an in-process control path looks like when the
provider does support updates, which is what a file-based or
environment-variable provider should be able to do.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.provider_tck import (
    Capability,
    InProcessControl,
    KnownDeviation,
    TckConfig,
    features_path,
)


@pytest.fixture(scope="session")
def tck_config(tck_known_deviations: tuple[KnownDeviation, ...]) -> TckConfig:
    """Declare the provider under test and what it can do.

    ``STALE`` and ``UNAVAILABLE_INIT`` stay undeclared: there is still no
    connection to lose, and ``InProcessControl`` does not implement
    ``ConnectionControl``. ``CONFIGURATION_CHANGE`` is what this suite adds over
    the plain in-memory one, and it is the whole point of it.

    ``LIFECYCLE`` stays undeclared for the same reason as in
    ``test_in_memory_conformance``: there is no backend to reach during
    initialisation, so the readiness scenario would pass here without testing
    anything. It did exactly that while the feature was gated on ``@events``.
    """
    control = InProcessControl()
    return TckConfig(
        name="controllable-in-memory",
        control=control,
        new_provider=control.new_provider,
        capabilities={
            Capability.EVENTS,
            Capability.CONFIGURATION_CHANGE,
            Capability.OBJECT,
            Capability.NUMERIC_COERCION,
        },
        # The same SDK bug, against the same issue: it is a defect in the client
        # rather than in either provider, so both suites acknowledge it.
        known_deviations=tck_known_deviations,
    )


scenarios(features_path())
