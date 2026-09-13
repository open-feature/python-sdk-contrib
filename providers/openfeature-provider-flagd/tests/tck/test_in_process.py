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
#   LIFECYCLE
#     Declared on a run, and the run is the point: this capability had been
#     withheld here since the first pass with nothing anywhere saying why, so
#     the six lifecycle scenarios had never been put to this resolver at all.
#     Declaring it and running them settles it -- all six execute and all six
#     pass. There was no reason; there was an omission that every later pass
#     inherited because the file next door treated it as given.
#
#     It is a real question here rather than a formality, which is the test the
#     capability's own documentation sets. An SDK synthesises PROVIDER_READY
#     around `initialize` for any provider, so the readiness scenario is vacuous
#     for a provider that does nothing during initialisation -- a NoOpProvider
#     passes it. This resolver syncs the entire ruleset and applies it to the
#     evaluator before ready is emitted (grpc_watcher.py:254-262), and
#     initialisation can and does fail (grpc_watcher.py:151), so both terminal
#     outcomes the feature file asserts are outcomes this provider actually
#     reaches.
#
#     Java, Go and JavaScript all declare it on both resolvers, and Go's
#     adoption records having made and reverted this exact mistake: withholding
#     it left that suite blind to six scenarios another language was running
#     against the same provider. Python was the last of the four still doing so.
#
#   NUMERIC_COERCION
#     Declared here and declared on RPC too, but they are not the same claim,
#     and that is the most interesting thing in this pair of suites: **this
#     resolver satisfies the lossy half and RPC does not.** Measured, both
#     resolvers, same run -- `float-flag` (0.5) requested as an Integer is a
#     TYPE_MISMATCH returning the caller's default here, and comes back as `0`
#     with no error code at all on RPC. One provider, two resolvers, opposite
#     answers to the question the capability exists to ask.
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
#     flagd-testbed seeds no `integral-float-flag`, so it fails FLAG_NOT_FOUND
#     (`Flag with key integral-float-flag not present in flag store.`), the same
#     backend gap the conftest records for `large-integer-flag`. What this
#     resolver would do with a seeded 10.0 is still unmeasured -- the `(int,)`
#     rule above says it would refuse it, but that is a reading of the source
#     and nothing here observes it. The gap is recorded rather than treated as a
#     reason to withhold: two of the three scenarios do reach this provider and
#     both pass, and withholding on the strength of the one the backend cannot
#     ask would discard the finding that the two resolvers differ.
#
#   REINITIALIZATION
#     New at spec@fc99d5ac, which gated the scenario "A provider that was shut
#     down can be initialized again" that had been untagged before it. Declared
#     here and withheld on RPC, and again the two resolvers genuinely differ:
#     this one shuts down and starts again serving `boolean-flag` correctly,
#     while RPC evaluates against a closed channel. Measured on the same run.
#
#     This was withheld until this pass, on the argument that declaring it would
#     be vacuous -- the scenario also carries @lifecycle, which this suite did
#     not declare, so it would have skipped on that tag regardless. The argument
#     was sound and is now spent: @lifecycle is declared above, the scenario
#     runs, and the claim is examined rather than asserted.
#
#     Requirement 2.5.2 says a provider SHOULD revert to its uninitialized
#     state and that "some providers MAY allow reinitialization", so reuse is
#     permitted rather than required -- which is why RPC's withholding needs no
#     KnownDeviation, and why declaring it here is a claim worth making rather
#     than a mandatory box ticked.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld, and this is a change: it was declared here until this pass and
#     failed on every run. Exactly one scenario carries the tag, and it asks for
#     `huge-integer-flag`, which flagd-testbed v3.8.0 does not seed -- so the
#     declaration was a claim with no evidence behind it either way, and its
#     failure (`Flag with key huge-integer-flag not present in flag store.`)
#     read as a provider defect while establishing nothing about the provider.
#     Python's `int` is unbounded and the ruleset arrives as JSON text parsed
#     with `json.loads` (flagd_core.py:73), so nothing here would narrow the
#     value; the suite simply cannot show that.
#
#     The rule this and NUMERIC_COERCION are both decided by is **Appendix F's
#     sixth declaring rule** -- once a provider is attempting a capability,
#     declare it when at least one scenario gating it can actually be put to the
#     provider and withhold only when none can, the unit being the scenario and
#     not the tag. It is cited rather than restated: the wording these two suites
#     used last pass is what went into the appendix at spec@4cab0320, so the
#     appendix is now where it lives and a copy here would be a second place for
#     it to drift.
#
#     The opening clause matters and was added at spec@aa2ad24f after the Go
#     implementation found the rule forcing declarations it should not: it
#     decides whether a question is *askable*, not whether the provider owes an
#     answer, and that second question comes first. Both tags clear it here --
#     this resolver does coerce, correctly in both directions it can be asked,
#     and nothing about it declines to resolve a large integer -- so what is left
#     for rule six to decide is the fixture gap. The two gaps look like the same
#     missing-fixture problem and are not. @numeric-coercion has three scenarios
#     and this backend can ask two of them, which is what makes the declaration
#     mean something and the third failure a footnote. @large-integers has one,
#     and this backend can ask none of it.
#
#     No KnownDeviation for it, in either shape. That is the rule's first
#     consequence: a scenario failing because the backend serves no fixture for
#     it is not a provider defect, and an entry would attribute the testbed's gap
#     to the provider. Go and JavaScript withhold it for this same reason; Java
#     cannot declare it at all, because its integer accessor is 32 bits, which is
#     a third thing again and not this one.
#
#     And the second consequence, which this sentence exists to satisfy: a
#     capability withheld for a backend gap is temporary in a way one withheld by
#     choice is not. open-feature/flagd-testbed#392 adds `huge-integer-flag`;
#     declare the tag when the image carries it, or this withholding outlives its
#     reason and starts reading as a claim about the provider.
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

    ``tck_backend`` is the TCK's own session-scoped fixture: it has already
    started the Compose file ``tests/tck/conftest.py`` declares, discovered the
    dynamically mapped host ports, built the control against the launchpad and
    waited for it to accept commands.
    """
    return build_config(IN_PROCESS_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
