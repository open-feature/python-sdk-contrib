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
    TckConfig,
    features_path,
)


@pytest.fixture(scope="session")
def tck_config() -> TckConfig:
    """Declare the provider under test and what it can do.

    ``STALE`` and ``UNAVAILABLE_INIT`` stay undeclared: there is still no
    connection to lose, and ``InProcessControl`` does not implement
    ``ConnectionControl``. ``CONFIGURATION_CHANGE`` is what this suite adds over
    the plain in-memory one, and it is the whole point of it.

    ``LIFECYCLE`` stays undeclared for the same reason as in
    ``test_in_memory_conformance``: there is no backend to reach during
    initialisation, so the readiness scenario would pass here without testing
    anything. It did exactly that while the feature was gated on ``@events``.

    ``NUMERIC_COERCION`` stays undeclared for the reason given there too.
    ``ControllableInMemoryProvider`` changes nothing about resolution, so it
    inherits the SDK provider's refusal to coerce: ``10.0`` requested as an
    integer is a ``TYPE_MISMATCH`` rather than ``10``. ``LARGE_INTEGERS`` is
    declared, since a Python ``int`` is exact at 2^53 - 1.

    ``TARGETING`` stays undeclared for the reason given there as well: this is
    the same decoded flag set, and it ignores ``targeting-key-flag``'s rule.
    ``VARIANTS`` is declared, since the flag set is keyed by variant name.

    ``DISABLED_FLAGS`` stays undeclared for the reason given there too, and this
    class inherits it rather than choosing it: ``ControllableInMemoryProvider``
    changes only how the flag set is *replaced*, and resolution -- including the
    fact that ``InMemoryFlag.resolve`` never reads ``state`` -- is still the
    SDK's. Measured the same way, with the same four failures.
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
            Capability.VARIANTS,
            Capability.LARGE_INTEGERS,
        },
    )


scenarios(features_path())
