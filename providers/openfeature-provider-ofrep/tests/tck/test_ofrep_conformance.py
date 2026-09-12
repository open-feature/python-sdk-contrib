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

# Every capability below was declared, the suite run, and its scenarios seen to
# pass -- bar the one row named under VARIANTS, which fails on a flag the testbed
# does not seed. The code references say where the behaviour lives, so a reader
# can check a claim; they are not the evidence for it. That order is Appendix F's
# rule as of spec@26362f85, and this file used to state the reverse.
#
#   OBJECT
#     ofrep/__init__.py:105-113 resolves structured values, and the type check at
#     ofrep/__init__.py:248 admits `(dict, list)` for FlagType.OBJECT -- so a JSON
#     object comes back as one rather than being rejected or flattened.
#
#   VARIANTS
#     ofrep/__init__.py:160 carries the response's `variant` field into the
#     resolution details, and flagd names a variant for every flag it serves.
#     Seven of the outline's eight rows pass. The eighth asks for
#     large-integer-flag's `max-int32` and fails with the flag missing from the
#     backend -- flagd-testbed v3.8.0 seeds neither large-integer-flag nor
#     huge-integer-flag, which already fails the untagged precision scenario
#     here and does the same in both flagd suites. Withholding the capability
#     over it would say this provider does not name variants, which the other
#     seven rows show is false, and would blame a missing flag on a capability
#     the provider has. It is not a KnownDeviation either: a deviation is for a
#     behaviour the provider is required to have and does not.
#
#   TARGETING
#     ofrep/__init__.py:229-230 puts the evaluation context's targeting key into
#     the request body's `context` object, so flagd evaluates
#     targeting-key-flag's rule against it. All three scenarios pass -- the
#     matching context, the non-matching one and no context at all -- which is
#     what makes context passthrough observable here without an echo endpoint:
#     a provider that dropped the context would resolve `miss` where `hit` is
#     expected.
#
#     Worth noting for a protocol with no types on the wire: the whole of what
#     is verified is that the key reached flagd, since nothing else about the
#     context is keyed on by any canonical flag.
#
# NUMERIC_COERCION is withheld, and the reason is worth recording because two
# other languages answered it differently over the same protocol.
#
# The capability has three scenarios and errors.feature says a declarer must
# satisfy all three -- the two lossless rows exist precisely to catch the
# shortcut of rejecting every float. This provider takes that shortcut. It keeps
# the two numeric types strictly apart: json.loads yields `int` for 10 and
# `float` for 0.5, and the check at ofrep/__init__.py:249-256 admits a value only
# on an exact isinstance against one of them. Nothing in that path widens or
# narrows a number. So the lossy row passes -- float-flag asked for as an Integer
# is a TYPE_MISMATCH rather than a silent 0 -- and integer-flag asked for as a
# Float fails, because 10 is not an instance of float.
#
# That is the same architecture as the Java OFREP adoption, which withholds the
# tag for the same reason: Jackson maps a JSON integer to Integer and a fraction
# to Double, and handleResolved admits the value only on an exact
# type.isInstance. The Go adoption declares it, and the difference is the JSON
# decoder rather than anything the provider author chose -- encoding/json makes
# every JSON number a float64, so integer-ness never survives the wire and
# ResolveInt has to round-trip through int64, which gives lossless coercion and a
# TYPE_MISMATCH on loss for free.
#
# Which is to say: over OFREP this capability follows the language's JSON
# library. Declaring it here would claim a behaviour two of these three lines of
# code rule out.
#
# No knownDeviation entry accompanies this. A deviation records a gap in
# behaviour the provider is required to have, and numeric coercion is a declared
# capability rather than a requirement -- Appendix F stopped presenting the rule
# as normative OpenFeature. The honest record is the undeclared tag and the three
# skips it produces.
#
#     Measured, and it does not support the declaration. One of the three
#     scenarios passes -- the lossy half, where rejecting 0.5 is correct -- and
#     the two lossless ones fail: integral-float-flag's 10.0 is a TYPE_MISMATCH
#     where 10 is required, and integer-flag's 10 is one where 10.0 is. That is
#     precisely the shortcut errors.feature warns of, "easy to get right by
#     rejecting every float", and its comment states that a provider declaring
#     the tag must satisfy all three.
#
#     The flagd suites reached this finding first and withdrew the tag for it:
#     "Neither resolver satisfies all three @numeric-coercion scenarios, so
#     neither declares it". The same conclusion follows here, and the same
#     withdrawal is the consistent end of it -- the two failures would become
#     skips carrying their reason, as they already do in both flagd suites. It is
#     left declared for now because withdrawing it is a change to what this
#     adoption claims rather than to how it is worded, and the claim is one to
#     settle deliberately rather than in passing. Until then this note is the
#     honest form of it: the tag is declared, the evidence is a run that fails.
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
#     the same declare-what-nothing-exercises error the reserved tag below is
#     kept out for.
#
#   CACHING
#     Reserved in the Capability enum; no scenario carries the tag. Declaring a
#     capability nothing exercises would be a claim with no evidence behind it.
#     @targeting was reserved alongside it until spec@26362f85 gave it three
#     scenarios, and is now declared above.
#
# The withheld set matches the Java OFREP adoption, which reached the same
# conclusions from the same architecture, independently. It differs from Go's,
# which declares NUMERIC_COERCION for the decoder reason recorded above.
CAPABILITIES = frozenset(
    {
        Capability.OBJECT,
        Capability.VARIANTS,
        Capability.TARGETING,
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
