"""The OpenFeature provider conformance suite, run against flagd's in-process resolver.

In-process syncs the whole ruleset over flagd's sync API and evaluates locally,
so unlike RPC the type-checking, the variant selection and the reason all come
from ``openfeature-flagd-core`` in this process rather than from the server. Any
difference in the results is a difference an application would see when it
switches resolver, which is why this is a separate suite rather than a
parametrisation of the RPC one.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.contrib.tools.tck import (
    Capability,
    RunningBackend,
    TckConfig,
    feature_paths,
)
from tests.tck.suite import IN_PROCESS_PORT, ResolverSuite, build_config

# Every capability below was declared, the suite run, and the scenarios seen to
# pass. The code references say where the behaviour lives, so a reader can check
# the claim -- they are not the evidence for it.
#
# The distinction is Appendix F's, stated there since spec@26362f85 and worth
# repeating here because this file used to get it backwards: source inspection is
# unreliable in both directions, which @reinitialization below shows from the
# other side -- this resolver does support reuse, and reading it does not say so.
#
#   EVENTS
#     grpc_watcher.py:262 emits PROVIDER_READY once the first sync payload has
#     been applied -- note "applied", not "received": the ruleset is written to
#     the evaluator at grpc_watcher.py:254 before ready is emitted, so a scenario
#     that evaluates immediately after ready cannot race the first sync.
#
#   STALE
#     grpc_watcher.py:178-190: the channel-connectivity callback emits
#     PROVIDER_STALE on TRANSIENT_FAILURE and starts a timer that escalates to
#     PROVIDER_ERROR only once retry_grace_period expires.
#
#   CONFIGURATION_CHANGE
#     in_process.py:34 emits PROVIDER_CONFIGURATION_CHANGED naming exactly the
#     keys that FlagdCore reports as changed, from every sync payload the watcher
#     applies.
#
#   OBJECT
#     in_process.py:122 resolves structured values from the local ruleset.
#
#   VARIANTS
#     flagd_core.py returns the variant name it selected with every resolution,
#     and in_process.py carries it into the resolution details. The ruleset is
#     keyed by variant, so there is always one to report.
#
#   DISABLED_FLAGS
#     New at spec@009afe06. All four rows pass, and here that is the
#     unsurprising half of the story: evaluation is local, so the resolver has
#     the flag's state and the caller's default in the same call.
#     flagd_core.py:143-145 returns the caller's `default_value` with reason
#     Reason.DISABLED the moment a flag's state is DISABLED, before any
#     targeting or variant selection. flagd_core.py:199-200 then skips the type
#     check for that reason, which is what stops the substituted default from
#     being re-typed against the flag it did not come from.
#
#     Probed directly, each of the four flags resolves to the caller's default
#     with reason Reason.DISABLED, no variant and no error code -- the SDK's
#     enum, where RPC hands back the server's bare 'DISABLED' string. Neither
#     is asserted by the scenarios and 2.2.5 requires neither, so the difference
#     is recorded rather than acted on. It is the sort of divergence between the
#     two resolvers this pair of suites exists to surface.
#
#   TARGETING
#     targeting.py:40-41 puts the evaluation context's targeting key into the
#     JSON-logic context under `targetingKey`, and flagd_core.py:154 evaluates
#     the flag's rule against it, so targeting-key-flag selects `hit` or `miss`
#     locally.
#
#   UNAVAILABLE_INIT
#     grpc_watcher.py:151 raises ProviderNotReadyError once the blocking init
#     deadline passes without a synced ruleset, which the SDK's registry turns
#     into PROVIDER_ERROR.
#
#   LARGE_INTEGERS
#     The ruleset arrives as JSON text over the sync stream and FlagdCore parses
#     it with `json.loads` (flagd_core.py:73), which gives an unbounded Python
#     int for 9007199254740991; nothing between the parser and the SDK routes
#     the value through a float or a 32-bit field.
#
# Not declared, and why:
#
#   NUMERIC_COERCION
#     Local, and strict in one direction only. flagd_core.py:25 admits only
#     `int` for an integer request and `_check_type` (flagd_core.py:228-231)
#     raises TypeMismatchError for anything else, so `float-flag`'s 0.5 is a
#     mismatch rather than 0 -- the lossy half holds. The float mapping at
#     flagd_core.py:26 is the wider `(int, float)`, and `resolve_float_value`
#     (flagd_core.py:113-114) widens an int result to a float, so `integer-flag`
#     requested as a Float is 10.0 -- that lossless half holds too. But the
#     same `(int,)` rule rejects `integral-float-flag`'s 10.0 requested as an
#     Integer, where the tag requires 10: two of three, and a declaration is
#     all or nothing. flagd's numeric-coercion ADR
#     (docs/architecture-decisions/numeric-coercion.md) commits every flagd
#     implementation to the lossless rule; when openfeature-flagd-core follows
#     it, this is declared again.
#
#   REINITIALIZATION
#     New at spec@fc99d5ac, which gated the scenario "A provider that was shut
#     down can be initialized again" that had been untagged before it. Withheld
#     here even though this resolver does support reuse, which is the
#     interesting half of the story and was measured rather than assumed:
#     declaring LIFECYCLE and REINITIALIZATION together locally makes the
#     scenario run, and in-process passes it, while RPC fails it against a
#     closed channel. The two resolvers genuinely differ.
#
#     It stays withheld because declaring it would be vacuous. The scenario
#     lives in lifecycle.feature, which carries @lifecycle at the feature level,
#     so it inherits that tag and carries both; the gate skips a scenario when
#     any capability gating it is undeclared, and this suite does not declare
#     LIFECYCLE. Declaring REINITIALIZATION alone would leave the scenario
#     skipped on @lifecycle and the claim unexamined -- the same
#     declare-what-nothing-exercises error the reserved tag below is kept out
#     for. Declaring LIFECYCLE is a separate question from this one and is not
#     settled here.
#
#     Requirement 2.5.2 says a provider SHOULD revert to its uninitialized
#     state and that "some providers MAY allow reinitialization", so reuse is
#     permitted rather than required and withholding needs no KnownDeviation.
#
#     Worth recording that this scenario never ran here, at this pin or the one
#     before it: it is one of the six @lifecycle skips each resolver reports,
#     not a scenario that used to pass.
#
#   STANDARD_REASONS
#     New at spec@c342461a, which moved every resolution-reason assertion out of
#     the other feature files and into reason.feature, gated as a whole. A claim
#     rather than an exemption: 2.2.5 is a SHOULD that permits "some other
#     string", so declaring the tag says this provider uses the standard
#     vocabulary with the standard meanings.
#
#     Declared on a run rather than on the source. All nine scenarios pass --
#     the four rule-less rows as STATIC, an unknown flag and a type mismatch as
#     ERROR beside their error codes, TARGETING_MATCH for the matched rule and
#     DEFAULT for the miss, DISABLED for a disabled flag. The last three need
#     @targeting and @disabled-flags as well, which this suite declares, so none
#     of the file is skipped here.
#
#     The DISABLED row resolves through Reason.DISABLED here, the SDK's own
#     enum, where RPC hands back flagd's bare 'DISABLED' string -- noted under
#     DISABLED_FLAGS above. The step compares the reason as text, so both pass.
#
#   CACHING
#     Reserved in the Capability enum; no scenario carries the tag. Declaring a
#     capability nothing exercises would be a claim with no evidence behind it,
#     so it is left out of both suites. @targeting was reserved alongside it
#     until spec@26362f85 gave it three scenarios, and is now declared above.
IN_PROCESS_CAPABILITIES = frozenset(
    {
        Capability.EVENTS,
        Capability.STALE,
        Capability.CONFIGURATION_CHANGE,
        Capability.OBJECT,
        Capability.VARIANTS,
        Capability.DISABLED_FLAGS,
        Capability.TARGETING,
        Capability.UNAVAILABLE_INIT,
        Capability.LARGE_INTEGERS,
        Capability.STANDARD_REASONS,
    }
)

IN_PROCESS_SUITE = ResolverSuite(
    name="flagd-in-process",
    resolver_type=ResolverType.IN_PROCESS,
    backend_port=IN_PROCESS_PORT,
    capabilities=IN_PROCESS_CAPABILITIES,
    # In-process transfers and applies the whole ruleset before reporting ready,
    # so it needs more headroom than RPC.
    ready_timeout=60.0,
)


@pytest.fixture(scope="session")
def tck_config(tck_backend: RunningBackend, closed_port: int) -> TckConfig:
    """The whole of this adoption's wiring.

    ``tck_backend`` is the TCK's own session-scoped fixture: it has already
    started the Compose file ``tests/tck/conftest.py`` declares, discovered the
    dynamically mapped host ports, built the control against the launchpad and
    waited for it to accept commands.
    """
    return build_config(IN_PROCESS_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
