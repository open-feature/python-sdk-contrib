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
# pass. The code references say where the behaviour lives, so that a reader can
# check the claim -- the run is what it rests on, which is Appendix F's rule and
# not a preference here. @reinitialization below shows why from the other side:
# this resolver does support reuse, and reading it does not say so.
#
#   EVENTS      grpc_watcher.py:262 emits PROVIDER_READY once the first sync
#               payload has been *applied*, not merely received: the ruleset is
#               written to the evaluator at grpc_watcher.py:254 first, so a
#               scenario evaluating straight after ready cannot race the sync.
#   STALE       grpc_watcher.py:178-190 emits PROVIDER_STALE on TRANSIENT_FAILURE
#               and starts the timer escalating to PROVIDER_ERROR only once
#               retry_grace_period expires.
#   CONFIGURATION_CHANGE
#               in_process.py:34 emits PROVIDER_CONFIGURATION_CHANGED naming
#               exactly the keys FlagdCore reports as changed, from every sync
#               payload the watcher applies.
#   OBJECT      in_process.py:122 resolves structured values from the local
#               ruleset.
#   VARIANTS    flagd_core.py returns the variant it selected with every
#               resolution and in_process.py carries it into the details; the
#               ruleset is keyed by variant, so there is always one to report.
#   TARGETING   targeting.py:40-41 puts the evaluation context's targeting key
#               into the JSON-logic context under `targetingKey` and
#               flagd_core.py:154 evaluates the rule against it, so
#               targeting-key-flag selects hit or miss locally.
#   UNAVAILABLE_INIT
#               grpc_watcher.py:151 raises ProviderNotReadyError once the
#               blocking init deadline passes without a synced ruleset, which the
#               SDK's registry turns into PROVIDER_ERROR.
#
#   DISABLED_FLAGS
#     All four rows pass, and here that is the unsurprising half of the story:
#     evaluation is local, so the resolver has the flag's state and the caller's
#     default in the same call. flagd_core.py:143-145 returns the caller's
#     `default_value` with reason Reason.DISABLED the moment a flag's state is
#     DISABLED, before any targeting or variant selection. flagd_core.py:199-200
#     then skips the type check for that reason, which is what stops the
#     substituted default from being re-typed against the flag it did not come
#     from.
#
#     Probed directly, each of the four flags resolves to the caller's default
#     with reason Reason.DISABLED, no variant and no error code -- the SDK's
#     enum, where RPC hands back the server's bare 'DISABLED' string. Nothing
#     asserts either, so the difference is recorded rather than acted on; it is
#     the sort of divergence between the two resolvers this pair of suites exists
#     to surface.
#
#   LIFECYCLE
#     All six scenarios execute and all six pass.
#
#     It is a real question here rather than a formality, which is the test the
#     capability's own documentation sets: an SDK synthesises PROVIDER_READY
#     around `initialize` for any provider, so the readiness scenario is vacuous
#     for a provider that does nothing during initialisation. This resolver syncs
#     the entire ruleset and applies it to the evaluator before ready is emitted
#     (grpc_watcher.py:254-262), and initialisation can and does fail
#     (grpc_watcher.py:151), so both terminal outcomes the feature file asserts
#     are outcomes this provider actually reaches.
#
#     Running them also produced a finding neither a pass nor a fail carries --
#     a shutdown-ordering race that leaves a stray traceback behind a *passing*
#     scenario. conftest.py records it; open-feature/python-sdk-contrib#419.
#
#   NUMERIC_COERCION
#     Declared here and declared on RPC too, but they are not the same claim,
#     and that is the most interesting thing in this pair of suites: **this
#     resolver satisfies the lossy half and RPC does not.** Measured, both
#     resolvers, same run -- `float-flag` (0.5) requested as an Integer is a
#     TYPE_MISMATCH returning the caller's default here, and comes back as `0`
#     with no error code at all on RPC. One provider, two resolvers, opposite
#     answers to the question the capability exists to ask
#     (open-feature/python-sdk-contrib#420).
#
#     Why it holds here: evaluation is local, so flagd_core.py:25 admits only
#     `int` for an integer request and `_check_type` (flagd_core.py:228-231)
#     raises TypeMismatchError for anything else. The float mapping at
#     flagd_core.py:26 is the wider `(int, float)` and `resolve_float_value`
#     (flagd_core.py:113-114) widens an int result, so `integer-flag` requested
#     as a Float is 10.0. Both of the scenarios this backend can put to the
#     provider pass, and no KnownDeviation is recorded against this resolver --
#     there is no defect here to record. The entry on the RPC suite is
#     deliberately not mirrored onto this one.
#
#     The tag's third scenario fails, and not for a reason about coercion:
#     flagd-testbed seeds no `integral-float-flag`, so it fails FLAG_NOT_FOUND.
#     What this resolver would do with a seeded 10.0 is still unmeasured -- the
#     `(int,)` rule above says it would refuse it, but that is a reading of the
#     source and nothing here observes it. Withholding the tag over the one
#     scenario this backend cannot ask would discard the finding that the two
#     resolvers differ.
#
#   REINITIALIZATION
#     Declared here and withheld on RPC, and again the two resolvers genuinely
#     differ: this one shuts down and starts again serving `boolean-flag`
#     correctly, while RPC evaluates against a closed channel. Measured on the
#     same run. Requirement 2.5.2 permits reuse rather than requiring it, which
#     is why RPC's withholding needs no KnownDeviation and why declaring it here
#     is a claim worth making rather than a box ticked.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld. Exactly one scenario carries the tag, it asks for
#     `huge-integer-flag`, and flagd-testbed v3.8.0 seeds no such flag -- so this
#     backend can put none of the tag's scenarios to this provider, and Appendix
#     F's sixth declaring rule says withhold. Python's `int` is unbounded and the
#     ruleset arrives as JSON text parsed with `json.loads` (flagd_core.py:73),
#     so nothing here would narrow the value -- and the suite cannot show that,
#     which is the point.
#
#     Contrast @numeric-coercion above, which is a fixture gap too and is
#     declared: two of its three scenarios do reach the provider, and the two
#     resolvers answer them differently. The rule counts scenarios, not tags.
#
#     No KnownDeviation, in either shape: the gap is the backend's and an entry
#     would attribute it to the provider. This withholding is temporary in a way
#     the ones above are not -- open-feature/flagd-testbed#392 adds the flag;
#     declare the tag when the image carries it, or it outlives its reason and
#     starts reading as a claim about the provider.
#
#   STANDARD_REASONS
#     Declared on a run rather than on the source. All nine scenarios pass -- the
#     four rule-less rows as STATIC, an unknown flag and a type mismatch as ERROR
#     beside their error codes, TARGETING_MATCH for the matched rule and DEFAULT
#     for the miss, DISABLED for a disabled flag. The last three need @targeting
#     and @disabled-flags as well, which this suite declares, so none of the file
#     is skipped here.
#
#     The DISABLED row resolves through Reason.DISABLED here, the SDK's own enum,
#     where RPC hands back flagd's bare 'DISABLED' string -- noted under
#     DISABLED_FLAGS above. The step compares the reason as text, so both pass.
#
#   CACHING
#     Reserved, and the harness refuses it: no scenario carries the tag.
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
        Capability.STANDARD_REASONS,
        Capability.LIFECYCLE,
        Capability.NUMERIC_COERCION,
        Capability.REINITIALIZATION,
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

    ``tck_backend`` is the TCK's own session-scoped fixture: the stack is up and
    its control is ready by the time this runs.
    """
    return build_config(IN_PROCESS_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
