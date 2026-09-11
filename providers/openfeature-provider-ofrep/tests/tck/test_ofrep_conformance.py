"""The OpenFeature provider conformance suite, run against the OFREP provider.

OFREP is the vendor-neutral remote evaluation protocol, so what is under test
here is a pure mapping: one HTTP request per evaluation, and the translation of
its JSON response -- or its error status -- into typed resolution details. There
is no cache, no stream and no local ruleset, so unlike the flagd suites there is
nothing here that a lifecycle could be wrong about.

The backend is flagd, which serves OFREP on port 8016 alongside its own
protocols, driven through the same launchpad control API and seeded with the
same canonical flag set as the flagd conformance suites. Running two providers
against one backend is the point of a cross-provider conformance suite: a
difference in the results is a difference an application would see when it
switches provider.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.contrib.tools.provider_tck import (
    Capability,
    TckConfig,
    features_path,
)
from openfeature.provider import FeatureProvider
from tests.tck.settled_control import SettledControl
from tests.tck.testbed import FlagdTestbed

TIMEOUT_SECONDS = 10.0
"""Bounds a single OFREP request.

Generous, because every scenario is preceded by a control-API ``/start`` that
restarts the flagd process, so the first evaluation of a scenario routinely hits
a backend that came up milliseconds ago. It is the only timing knob this
provider has (``ofrep/__init__.py:52``); everything else the TCK offers -- event
timeouts, ready timeouts -- has nothing to bound, for the reasons below.
"""

# Every capability below is declared on the strength of a line of provider code,
# not on the strength of a green run.
#
#   OBJECT
#     ofrep/__init__.py:105-113 resolves structured values, and the type check at
#     ofrep/__init__.py:248 admits `(dict, list)` for FlagType.OBJECT -- so a JSON
#     object comes back as one rather than being rejected or flattened.
#
#   NUMERIC_COERCION
#     ofrep/__init__.py:250 maps FlagType.INTEGER to `int`, and the isinstance
#     check at ofrep/__init__.py:255 fails for the float 0.5, raising
#     TypeMismatchError. So float-flag's 0.5 is reported as a mismatch rather
#     than narrowed to 0. Worth stating plainly that this is the provider's own
#     doing: OFREP is untyped on the wire, the request carries no type at all,
#     and flagd returns 0.5 whatever was asked for -- so unlike flagd-RPC, where
#     the server answers INVALID_ARGUMENT, there is no backend here to catch a
#     numeric mismatch. Every type decision in this suite is made at those two
#     lines, which is also why the one deviation recorded in conftest.py lives
#     there.
#
# Not declared, and why. Each is a fact about the provider, established by
# reading it -- OFREPProvider is stateless: it holds a requests.Session and a
# rate-limit timestamp, and nothing else survives between evaluations.
#
#   LIFECYCLE
#     OFREPProvider does not override `initialize`, so it inherits
#     AbstractProvider's, which is `pass` (python-sdk
#     openfeature/provider/__init__.py:138-139). Nothing contacts the backend
#     before the first evaluation, so initialisation has no outcome to observe.
#     lifecycle.feature carries @lifecycle at feature level and skips as a
#     whole, which is the intended outcome: it was gated on @events before the
#     capability was split out, and the retag had to keep it skipping here.
#
#   EVENTS
#     The provider never emits. It extends AbstractProvider, so it inherits
#     `attach`, but `_on_emit` is never called anywhere in
#     ofrep/__init__.py -- there is no stream, no poll and no background thread
#     to notice anything worth emitting about.
#
#     The SDK's registry does dispatch PROVIDER_READY around `initialize` for any
#     provider (python-sdk openfeature/provider/_registry.py:73-77), so declaring
#     EVENTS would make lifecycle.feature's readiness scenario pass without
#     demonstrating anything -- a NoOpProvider passes it identically. That is
#     exactly the vacuity the @lifecycle capability was split out to end, and
#     claiming the capability to collect the pass would be the dishonest use of
#     it.
#
#   STALE, CONFIGURATION_CHANGE
#     Both are event capabilities and follow from EVENTS. There is no connection
#     to lose -- every evaluation is an independent HTTP request -- so there is no
#     state between them that could go stale, and nothing watches the backend for
#     a configuration change. events.feature is gated @events at feature level
#     and skips as a whole.
#
#     Note that a *change* is nonetheless visible to an application: the next
#     evaluation issues a fresh request and returns the new value. What is
#     missing is the signal, and the @configuration-change scenario asserts the
#     event as well as the behaviour, deliberately -- a provider that changes
#     silently is not conformant, it is just not broken.
#
#   UNAVAILABLE_INIT
#     A provider pointed at a closed port reaches READY, because `initialize`
#     does nothing and the registry dispatches PROVIDER_READY unconditionally
#     (python-sdk openfeature/provider/_registry.py:73-77). The failure surfaces
#     on the first evaluation as GeneralError from ofrep/__init__.py:167, not as
#     PROVIDER_ERROR, so the scenario's premise does not hold. `TckConfig` also
#     rejects the capability without a `new_unavailable_provider`, and none is
#     supplied here for the same reason.
#
#   REINITIALIZATION
#     New at spec@fc99d5ac, which gated the scenario "A provider that was shut
#     down can be initialized again" that had been untagged before it.
#     Requirement 2.5.2 says a provider SHOULD revert to its uninitialized
#     state and that "some providers MAY allow reinitialization", so reuse is
#     permitted rather than required and withholding needs no KnownDeviation.
#
#     Reuse would in fact work here -- a stateless provider holding only a
#     Session has nothing to release and nothing to rebuild, and `shutdown` is
#     inherited and does nothing either -- but the scenario cannot be reached to
#     demonstrate it. It lives in lifecycle.feature, so it inherits @lifecycle
#     at feature level, and the gate skips a scenario when any capability
#     gating it is undeclared. With LIFECYCLE withheld above, declaring this
#     would leave the scenario skipped on @lifecycle and the claim unexamined:
#     the same declare-what-nothing-exercises error the reserved tags below are
#     kept out for.
#
#   TARGETING, CACHING
#     Reserved in the Capability enum; no scenario carries either tag. Declaring
#     a capability nothing exercises would be a claim with no evidence behind it.
#
# The result matches the Go and Java OFREP adoptions, which reached the same two
# capabilities from the same architecture, independently.
CAPABILITIES = frozenset(
    {
        Capability.OBJECT,
        Capability.NUMERIC_COERCION,
    }
)


@pytest.fixture(scope="session")
def tck_config(
    flagd_testbed: FlagdTestbed,
    ofrep_control: SettledControl,
) -> TckConfig:
    """Wire the provider up to the running testbed.

    The port is read here, after the stack is up: compose maps host ports
    dynamically, so it does not exist earlier -- and it stays valid for the whole
    session because nothing ever restarts a container. Outages, had this suite
    any use for them, would be simulated inside the running stack through
    ``ofrep_control``.
    """
    base_url = flagd_testbed.get_ofrep_url()

    def new_provider() -> FeatureProvider:
        return OFREPProvider(base_url, timeout=TIMEOUT_SECONDS)

    return TckConfig(
        name="ofrep",
        control=ofrep_control,
        new_provider=new_provider,
        capabilities=CAPABILITIES,
    )


scenarios(features_path())
