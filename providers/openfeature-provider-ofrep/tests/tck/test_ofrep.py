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
    BackendControl,
    Capability,
    TckConfig,
    feature_paths,
)
from openfeature.provider import FeatureProvider

TIMEOUT_SECONDS = 10.0
"""Bounds a single OFREP request.

Generous, because every scenario is preceded by a control-API ``/start`` that
restarts the flagd process. It is the only timing knob this provider has
(``ofrep/__init__.py:52``); everything the TCK offers -- event timeouts, ready
timeouts -- has nothing to bound here, for the reasons below.
"""

# Every capability below was declared, the suite run, and its scenarios seen to
# pass -- bar the one row named under VARIANTS, which fails on a flag the testbed
# does not seed. The code references say where the behaviour lives, so that a
# reader can check the claim; the run is what it rests on.
#
#   OBJECT      ofrep/__init__.py:105-113 resolves structured values, and the
#               type check at ofrep/__init__.py:248 admits `(dict, list)` for
#               FlagType.OBJECT -- so a JSON object comes back as one rather than
#               being rejected or flattened.
#   VARIANTS    ofrep/__init__.py:160 carries the response's `variant` into the
#               resolution details. Seven of the outline's eight rows pass; the
#               eighth asks for large-integer-flag's `max-int32`, which
#               no released flagd-testbed seeds (see conftest.py). Withholding
#               over it would say this provider does not name variants, which the
#               other seven rows show is false.
#   TARGETING   ofrep/__init__.py:229-230 puts the evaluation context's targeting
#               key into the request body's `context`, so flagd evaluates
#               targeting-key-flag's rule against it. All three scenarios pass --
#               the matching context, the non-matching one and no context at all
#               -- and for a protocol with no types on the wire that is the whole
#               of what is verified about passthrough: the key reached flagd.
#
#   STANDARD_REASONS
#     Eight of the file's nine scenarios run here and all eight pass: the four
#     rule-less rows as STATIC, an unknown flag and a type mismatch as ERROR
#     beside their error codes, and -- because TARGETING is declared above --
#     TARGETING_MATCH for the matched rule and DEFAULT for the miss. The ninth
#     composes with @disabled-flags, withheld below, so it skips with that reason.
#
#     **The obstacle that was expected here is not the one that exists**, and it
#     was measured rather than reasoned about. ofrep/__init__.py:159 indexes
#     `Reason[data["reason"]]` by *name*, so a server reporting a reason outside
#     the SDK's enum raises KeyError -- which is why this capability looked like
#     the risky one. It is not: every reason reason.feature asserts is an enum
#     member, DISABLED included. Declaring @disabled-flags alongside this one and
#     running the ninth scenario shows that index surviving the DISABLED reason
#     and the *next* keyword argument failing -- `variant=data["variant"]` on line
#     160, KeyError: 'variant', reported to the application as GENERAL. Same
#     one-line defect the @disabled-flags note below records, and nothing to do
#     with the reason vocabulary.
#
#   STRING_TYPING
#     Declared, on a run: all four scenarios pass -- three Examples rows asking
#     for `boolean-flag`, `integer-flag` and `float-flag` through the string
#     accessor, and the `@object` one asking for `object-flag`, which reaches
#     this suite because OBJECT is declared above.
#
#     **"Untyped protocol" is not the same claim as "untyped backend"**, and
#     this is the tag where the two come apart, so it is worth being explicit
#     rather than inheriting the sentence used elsewhere in this file. OFREP
#     carries no *requested* type on the wire -- which is exactly why
#     boolean-flag satisfies an Integer request here and is xfailed in
#     conftest.py -- but the response body is JSON, and JSON distinguishes
#     `true` from `"true"` and `10` from `"10"`. So the values this provider
#     receives are typed, and ofrep/__init__.py:249-256 checks them: FlagType
#     .STRING maps to the bare `str`, and a bool, a number or a structure fails
#     that isinstance and becomes TYPE_MISMATCH.
#
#     The capability is about the backend's storage rather than the protocol's
#     request envelope: the provider a string-storing backend produces answers
#     `"true"` to the string accessor and has nothing to reject. flagd holds
#     typed variants and serialises them as typed JSON, so this provider is
#     never handed one. That is a property of the stack rather than of OFREP,
#     and it is the reason the tag is declared on a run rather than argued from
#     the protocol -- the same protocol over a Flipt-like backend would be a
#     withholding.
#
#     Note how little of the bool-as-int defect carries over: `str` is not in
#     bool's ancestry, so the subclass hazard that makes the Integer accessor
#     admit `True` has no counterpart on the string accessor.
#
#     Four scenarios that were mandatory at the previous pin, and passing, so
#     the declaration keeps them running and changes no number: the full run is
#     2 failed, 45 passed, 17 skipped, 1 xfailed before and after.
#
# Not declared, and why.
#
#   NUMERIC_COERCION
#     Withheld, because this provider does not coerce at all -- which is the case
#     Appendix F reserves withholding for, and the reason the flagd adoption in
#     this repository reads the opposite way on the same rule.
#
#     A declarer must satisfy all three scenarios; the two lossless rows exist to
#     catch the shortcut of rejecting every float, and this provider takes that
#     shortcut. It keeps the two numeric types strictly apart: json.loads yields
#     `int` for 10 and `float` for 0.5, and the check at
#     ofrep/__init__.py:249-256 admits a value only on an exact isinstance
#     against one of them. Nothing in that path widens or narrows. So the lossy
#     row passes -- float-flag asked for as an Integer is a TYPE_MISMATCH rather
#     than a silent 0 -- and integer-flag asked for as a Float fails, because 10
#     is not an instance of float. Over OFREP the capability follows the
#     language's JSON library rather than anything the provider author chose.
#
#     No KnownDeviation: nothing requires numeric coercion, so there is no
#     requirement to deviate from. The honest record is the undeclared tag and
#     the three skips it produces.
#
#   DISABLED_FLAGS
#     Withheld, and **this is the one declaration in these suites that should
#     change shape**: the provider attempts the behaviour and fails on one
#     unconditional index, which is the declare-and-deviate case rather than the
#     withhold case. It is left standing only because the pass that found it was a
#     documentation pass and changing it moves a count; PR #414 records the
#     decision, and the next change here declares the tag, accepts four failing
#     rows and records the defect as a deviation.
#
#     Measured, then read back, then probed at the wire. Declaring the tag fails
#     all four rows, each on the error code rather than the value: "error-code was
#     'GENERAL', expected none" (probed at 56 collected, before reason.feature
#     took the suite to 65; the four rows move from skipped to failed and nothing
#     else changes). flagd's OFREP endpoint answers a disabled flag
#     `200 {"key": ..., "reason": "DISABLED", "metadata": {}}` -- no `value` and
#     no `variant`. The absent value is not the obstacle:
#     ofrep/__init__.py:153 already reads `data.get("value", default_value)` and
#     the type check on the next line passes on it. What fails is
#     ofrep/__init__.py:160, indexing `data["variant"]` unconditionally, where
#     types.md types the field `variant (string, optional)`. **The whole of the
#     difference between passing and failing these four rows is one `.get`**, and
#     the same index breaks on any variant-less OFREP response, not only a
#     disabled flag. Filed as open-feature/python-sdk-contrib#418.
#
#     So the capability is within reach of this provider rather than outside it,
#     and flagd's RPC resolver satisfies the tag from the same signal in a
#     different envelope.
#
#   Everything below follows from the provider being stateless: it holds a
#   requests.Session and a rate-limit timestamp, and nothing else survives
#   between evaluations.
#
#   LIFECYCLE
#     OFREPProvider does not override `initialize`, so it inherits
#     AbstractProvider's, which is `pass` (python-sdk
#     openfeature/provider/__init__.py:138-139). Nothing contacts the backend
#     before the first evaluation, so initialisation has no outcome to observe,
#     and lifecycle.feature -- which carries @lifecycle at feature level -- skips
#     as a whole.
#
#   EVENTS
#     The provider never emits: it inherits `attach` from AbstractProvider, but
#     `_on_emit` is never called anywhere in ofrep/__init__.py, because there is
#     no stream, no poll and no background thread to notice anything.
#
#     The SDK's registry does dispatch PROVIDER_READY around `initialize` for any
#     provider (python-sdk openfeature/provider/_registry.py:73-77), so declaring
#     EVENTS would make the readiness scenario pass without demonstrating
#     anything -- a NoOpProvider passes it identically. That is the vacuity
#     @lifecycle was split out to end.
#
#   STALE, CONFIGURATION_CHANGE
#     Both follow from EVENTS. There is no connection to lose -- every evaluation
#     is an independent HTTP request -- so no state between them can go stale, and
#     nothing watches the backend for a change. events.feature is gated @events at
#     feature level and skips as a whole.
#
#     Note that a *change* is nonetheless visible to an application: the next
#     evaluation issues a fresh request and returns the new value. What is missing
#     is the signal, and the @configuration-change scenario asserts the event as
#     well as the behaviour, deliberately.
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
#     Reuse would in fact work -- a stateless provider holding only a Session has
#     nothing to release and nothing to rebuild, and `shutdown` is inherited and
#     does nothing either -- but the scenario cannot be reached to demonstrate it:
#     it inherits @lifecycle from its feature, withheld above, so declaring this
#     would leave the scenario skipped and the claim unexamined. Requirement 2.5.2
#     permits reuse rather than requiring it, so withholding needs no
#     KnownDeviation.
#
#   LARGE_INTEGERS
#     The one withholding here that is about the backend rather than the provider.
#     Exactly one scenario carries the tag, it asks for `huge-integer-flag`, and
#     no released flagd-testbed seeds such a flag -- so none of the tag's scenarios
#     can be put to this provider, and Appendix F's sixth declaring rule says
#     withhold. Contrast VARIANTS above, where seven of eight rows do reach the
#     provider and the tag is declared on their strength.
#
#     Nothing in this path would narrow the value: a JSON number decodes through
#     `json.loads` into an unbounded Python `int` and the type check at
#     ofrep/__init__.py:249-256 admits it unchanged -- and the suite cannot show
#     that, which is the point.
#
#     No KnownDeviation, in either shape: the gap is the fixture's and an entry
#     would attribute it to the provider. Unlike the withholdings above, this one
#     is temporary -- open-feature/flagd-testbed#392 adds the flag; declare the
#     tag when the image carries it, or it outlives its reason and starts reading
#     as a claim about the provider.
#
#   CACHING
#     Reserved, and the harness refuses it: no scenario carries the tag.
CAPABILITIES = frozenset(
    {
        Capability.OBJECT,
        Capability.VARIANTS,
        Capability.STRING_TYPING,
        Capability.TARGETING,
        Capability.STANDARD_REASONS,
    }
)


@pytest.fixture(scope="session")
def tck_config(
    ofrep_base_url: str,
    ofrep_control: BackendControl,
) -> TckConfig:
    """Wire the provider up to the running testbed.

    Both fixtures come from ``tests/tck/conftest.py`` and both resolve after the
    TCK has started the stack, which is when the mapped host port exists.
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
