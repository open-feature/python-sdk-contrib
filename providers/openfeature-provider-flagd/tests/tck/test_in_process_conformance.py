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
from openfeature.contrib.tools.provider_tck import (
    Capability,
    HttpControl,
    TckConfig,
    features_path,
)
from tests.e2e.flagd_container import FlagdContainer
from tests.tck.suite import ResolverSuite, build_config

# Every capability below is declared on the strength of a line of provider code,
# not on the strength of a green run.
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
#     declare-what-nothing-exercises error the reserved tags below are kept out
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
#   TARGETING, CACHING
#     Reserved in the Capability enum; no scenario carries either tag. Declaring
#     a capability nothing exercises would be a claim with no evidence behind it,
#     so they are left out of both suites.
IN_PROCESS_CAPABILITIES = frozenset(
    {
        Capability.EVENTS,
        Capability.STALE,
        Capability.CONFIGURATION_CHANGE,
        Capability.OBJECT,
        Capability.UNAVAILABLE_INIT,
        Capability.LARGE_INTEGERS,
    }
)

IN_PROCESS_SUITE = ResolverSuite(
    name="flagd-in-process",
    resolver_type=ResolverType.IN_PROCESS,
    capabilities=IN_PROCESS_CAPABILITIES,
    # In-process transfers and applies the whole ruleset before reporting ready,
    # so it needs more headroom than RPC.
    ready_timeout=60.0,
)


@pytest.fixture(scope="session")
def tck_config(
    flagd_testbed: FlagdContainer,
    flagd_control: HttpControl,
    closed_port: int,
) -> TckConfig:
    return build_config(IN_PROCESS_SUITE, flagd_testbed, flagd_control, closed_port)


scenarios(features_path())
