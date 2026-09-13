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
from openfeature.contrib.tools.tck import (
    Capability,
    TckConfig,
    feature_paths,
)
from openfeature.provider import FeatureProvider
from tests.tck.settled_control import SettledControl

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
#   STANDARD_REASONS
#     New at spec@c342461a, which moved every resolution-reason assertion out of
#     the other feature files and into reason.feature, gated as a whole. A claim
#     rather than an exemption: 2.2.5 is a SHOULD that permits "some other
#     string", so declaring the tag says this provider uses the standard
#     vocabulary with the standard meanings.
#
#     Eight of the file's nine scenarios run here and all eight pass: the four
#     rule-less rows as STATIC, an unknown flag and a type mismatch as ERROR
#     beside their error codes, and -- because TARGETING is declared above --
#     TARGETING_MATCH for the matched rule and DEFAULT for the miss. The ninth
#     composes with @disabled-flags, withheld below, so it is skipped with that
#     reason.
#
#     The obstacle that was expected here is not the one that exists, and it was
#     measured rather than reasoned about. ofrep/__init__.py:159 indexes
#     `Reason[data["reason"]]` by *name*, so a server reporting a reason outside
#     the SDK's enum raises KeyError -- which is why this capability looked like
#     the risky one. It is not: every reason reason.feature asserts is an enum
#     member, DISABLED included. Declaring @disabled-flags alongside this one and
#     running the ninth scenario shows the index surviving the DISABLED reason
#     and the *next* keyword argument failing, `variant=data["variant"]` on line
#     160, with KeyError: 'variant' reported to the application as GENERAL. That
#     is the same one-line defect the @disabled-flags note below records, and it
#     is unrelated to the reason vocabulary.
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
# This withholding survives the correction that appendix made at spec@045950ca,
# and it is worth saying which side of it this is on, because the flagd adoption
# in this repository reads the opposite way. That note now says a provider which
# *attempts* the coercion and gets a direction wrong declares the tag and lets
# the scenario fail -- flagd's RPC resolver narrows 0.5 to 0 and does exactly
# that -- and that withholding is for a provider which cannot attempt it at all.
# This provider is the second kind: it never widens or narrows anything, the two
# JSON types stay apart end to end, and there is no coercion here to get wrong.
# Same rule, different provider, opposite answer.
#
# DISABLED_FLAGS is withheld as well, new at spec@009afe06, and this one is a
# provider defect rather than an architecture. Which is the opposite of what the
# appendix predicts, so it is worth being exact about.
#
# The appendix gates the tag on the reasoning that a provider "whose backend
# decides, such as one speaking OFREP, cannot: the server never sees the
# caller's default, so it has no way to return it". Neither half of that is the
# obstacle here.
#
# Measured first. Declaring the tag fails all four rows -- 6 failed, 37 passed,
# 12 skipped, 1 xfailed, against the 2 failed of the run without it -- and each
# fails on the error code rather than on the value: "error-code was 'GENERAL',
# expected none". Then read back, and probed at the wire to be sure of the
# reading. flagd's OFREP endpoint answers a disabled flag
# `200 {"key": ..., "reason": "DISABLED", "metadata": {}}`: no `value`, and no
# `variant`. The server does indeed never return a value, exactly as the
# appendix says. It does not need to -- ofrep/__init__.py:153 already reads
# `data.get("value", default_value)` and substitutes the caller's default for an
# absent one, and the type check on the next line passes on it.
#
# What fails is ofrep/__init__.py:160, which indexes `data["variant"]`
# unconditionally. flagd omits the member for a disabled flag, types.md types
# the field `variant (string, optional)`, and the resolution raises
# KeyError: 'variant'; the SDK catches it and reports GENERAL. So the whole of
# the difference between passing and failing these four rows is one `.get`.
#
# Which puts the capability within reach of this provider rather than outside
# it, and flagd's own RPC resolver satisfies the tag from the same signal in a
# different envelope. It is withheld because a declaration has to rest on a run
# and the run fails -- not because the architecture forbids it. The gap is an
# unfiled defect in openfeature-provider-ofrep, and it is not confined to
# disabled flags: the same index breaks on any OFREP response that omits the
# variant, which the field being optional permits for any reason a server
# reports without one.
#
# No knownDeviation entry, for the reason the numeric-coercion note above gives:
# a deviation records a gap in behaviour the provider is required to have, and
# @disabled-flags is a declared capability rather than a requirement. The honest
# record is the undeclared tag, the four skips it produces, and this note saying
# the gap is a bug somebody can fix rather than a fact of the protocol.
#
# **That reasoning does not survive spec@045950ca, and this is the one decision
# in these suites that the corrected appendix says should change.** It is left
# standing here only because the pass that found it was a documentation pass and
# changing it moves a count. The difference from the numeric-coercion note above
# is that this provider *does* attempt the behaviour: it resolves a disabled flag
# and gets it wrong on one unconditional index, which is the case the appendix
# tells an adopter to declare and let fail, with a KnownDeviation.untracked
# beside it -- "withdrawing the capability replaces a failing scenario with a
# skip and hides a defect behind something that looks deliberate". The self-test
# carve-out in that same revision, which does license a withholding for an
# identified defect, is explicit that an adoption has none: this suite exists to
# report on a provider, and a skip here is a claim about that provider.
#
# So the next change to this file declares @disabled-flags, accepts four failing
# rows, and records the `data["variant"]` defect as an untracked deviation -- and
# files it, which is what makes the deviation tracked and the failures temporary.
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
#   LARGE_INTEGERS
#     The one withholding in this list that is about the backend rather than the
#     provider, and until this pass the one with no reason written down at all.
#     Appendix F's sixth declaring rule (spec@4cab0320) is what decides it:
#     exactly one scenario carries the tag, it asks for `huge-integer-flag`, and
#     flagd-testbed v3.8.0 seeds no such flag -- so not one of the tag's
#     scenarios can be put to this provider, and nothing about the capability
#     can be established either way. Contrast VARIANTS above, where seven of
#     eight rows do reach the provider and the tag is declared on their strength.
#
#     Nothing in this path would narrow the value: a JSON number decodes through
#     `json.loads` into an unbounded Python `int` and the type check at
#     ofrep/__init__.py:249-256 admits it unchanged. The suite cannot show that,
#     which is the point -- a declaration would be a claim with no evidence
#     behind it in either direction.
#
#     No KnownDeviation, in either shape: the gap is the fixture's, and an entry
#     would attribute it to the provider. And per the same rule's second
#     consequence this withholding is temporary in a way the ones above are not.
#     open-feature/flagd-testbed#392 adds the flag; declare the tag when the
#     image carries it, or this outlives its reason and starts reading as a
#     claim about the provider. Both flagd suites here withhold it on the same
#     ground and say so in the same terms.
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
        Capability.STANDARD_REASONS,
    }
)


@pytest.fixture(scope="session")
def tck_config(
    ofrep_base_url: str,
    ofrep_control: SettledControl,
) -> TckConfig:
    """Wire the provider up to the running testbed.

    Both fixtures come from ``tests/tck/conftest.py`` and both resolve after the
    TCK has started the stack: Compose maps host ports dynamically, so the
    address does not exist earlier -- and it stays valid for the whole session
    because nothing ever restarts a container. Outages, had this suite any use
    for them, would be simulated inside the running stack through
    ``ofrep_control``.
    """
    base_url = ofrep_base_url

    def new_provider() -> FeatureProvider:
        return OFREPProvider(base_url, timeout=TIMEOUT_SECONDS)

    return TckConfig(
        name="ofrep",
        control=ofrep_control,
        new_provider=new_provider,
        capabilities=CAPABILITIES,
    )


scenarios(*feature_paths())
