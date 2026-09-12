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
def tck_config() -> TckConfig:
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
    * ``TARGETING`` -- omitted because this flag set has no targeting rule to
      resolve. ``canonical-flags.json`` gives ``targeting-key-flag`` one, and
      ``_decode_canonical_flags`` deliberately ignores the member: decoding a
      rule language would make this package a second implementation of somebody
      else's evaluator. So the flag is served at its ``miss`` default whatever
      the context, the matching-context scenario would fail, and withholding
      the capability is the honest report. That is a property of this in-memory
      flag set rather than a defect in the SDK's provider, which is why nothing
      here is a ``KnownDeviation``.
    * ``CACHING`` -- omitted because no scenario carries the tag yet, so leaving
      it out skips nothing. It is also reserved, so declaring it is refused.
    * ``LIFECYCLE`` -- omitted because there is no backend to reach. The
      capability asserts that initialisation actually contacts a backend and
      that the outcome is observable; this provider's ``initialize`` is a no-op
      and the SDK dispatches ``PROVIDER_READY`` around it regardless, so the
      readiness scenario would pass here without testing anything. It passed
      vacuously while the feature was gated on ``EVENTS``, which is precisely
      the failure mode the split of ``@lifecycle`` from ``@events`` exists to
      end. A skip with a reason is the honest outcome.
    * ``DISABLED_FLAGS`` -- omitted because the SDK's in-memory provider ignores
      a flag's ``state``. ``InMemoryFlag`` has a ``State`` enum with a
      ``DISABLED`` member, ``_decode_canonical_flags`` reads the canonical
      file's ``"state": "DISABLED"`` and passes it through faithfully, and
      ``InMemoryFlag.resolve`` never looks at it -- so all four ``disabled-*``
      flags are served at their own default variant with reason ``STATIC``,
      where the scenarios expect the caller's default. Measured before it was
      gated: the four rows failed on the value, ``disabled-boolean-flag``
      resolving to ``True`` against a caller default of ``false``. The
      capability is optional, so the honest report is a withheld declaration
      rather than a ``KnownDeviation`` -- but unlike ``NUMERIC_COERCION`` this
      one is a field the SDK offers and does not honour, which is finding 4 in
      the README.
    * ``NUMERIC_COERCION`` -- omitted because the SDK's in-memory provider does
      not coerce. It hands each variant back untouched, and the client's type
      check is ``isinstance``-based, so ``integral-float-flag`` (``10.0``)
      requested as an integer is a ``TYPE_MISMATCH`` rather than ``10``, and
      ``integer-flag`` (``10``) requested as a float is one rather than
      ``10.0``. The lossy scenario passes for the wrong reason -- every float
      is rejected -- which is exactly what the two lossless scenarios exist to
      catch, and declaring the tag would have them catch it here. The
      capability is optional, so this is a choice the provider is entitled to
      rather than a deviation.

    ``LARGE_INTEGERS`` is declared: a Python ``int`` is unbounded and nothing
    in this provider routes a value through a float. ``VARIANTS`` is declared
    too: the in-memory flag set is keyed by variant name, so the provider has
    one to report for every flag and does.
    """
    return TckConfig(
        name="in-memory",
        control=PlainMemoryControl(),
        new_provider=_new_provider,
        capabilities={
            Capability.EVENTS,
            Capability.OBJECT,
            Capability.VARIANTS,
            Capability.LARGE_INTEGERS,
        },
    )


scenarios(features_path())
