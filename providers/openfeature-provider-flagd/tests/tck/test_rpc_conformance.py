"""The OpenFeature provider conformance suite, run against flagd's RPC resolver.

RPC asks flagd to evaluate each flag over gRPC and maps the response onto typed
resolution details, so what is under test here is that mapping plus the
lifecycle the evaluation stream drives.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.contrib.tools.tck import (
    Capability,
    KnownDeviation,
    RunningBackend,
    TckConfig,
    feature_paths,
)
from tests.tck.suite import RPC_PORT, ResolverSuite, build_config

# Every capability below was declared, the suite run, and the scenarios seen to
# pass. The code references say where the behaviour lives, so a reader can check
# the claim -- they are not the evidence for it.
#
# The distinction is Appendix F's, stated there since spec@26362f85 and worth
# repeating here because this file used to get it backwards: source inspection is
# unreliable in both directions. @reinitialization below is the case in point --
# RPC's shutdown reverts enough of its own state to read as support for reuse,
# and the channel underneath cannot be rebuilt.
#
#   EVENTS
#     grpc.py:261 emits PROVIDER_READY when the evaluation stream delivers its
#     'provider_ready' message.
#
#   STALE
#     grpc.py:202-212: the channel-connectivity callback emits PROVIDER_STALE on
#     TRANSIENT_FAILURE and only then starts a timer that escalates to
#     PROVIDER_ERROR once retry_grace_period expires.
#
#     Worth calling out, because the Go provider does NOT do this: its RPC
#     resolver sends ProviderError directly on connection loss and never emits
#     PROVIDER_STALE, which is filed as go-sdk-contrib#939 and is why the Go
#     adoption withholds this capability for RPC. Python has no such asymmetry --
#     both of its resolvers share the same state-change callback shape -- so the
#     capability is declared here.
#
#   CONFIGURATION_CHANGE
#     grpc.py:302 emits PROVIDER_CONFIGURATION_CHANGED with the changed keys, and
#     grpc.py:298-300 evicts exactly those keys from the LRU cache, so the
#     re-evaluation the scenario performs afterwards cannot be served a stale
#     cached value.
#
#   OBJECT
#     grpc.py:336 resolves structured values through ResolveObject.
#
#   VARIANTS
#     grpc.py:449 carries the response's `variant` field into the resolution
#     details for every typed call, and flagd names a variant for every flag in
#     the testbed's set.
#
#   DISABLED_FLAGS
#     New at spec@009afe06. All four rows pass, which is worth saying plainly
#     because the appendix's own rationale for gating the tag predicts they
#     would not: it reasons that a provider "whose backend decides, such as one
#     speaking OFREP", cannot substitute a default the server never saw. RPC is
#     a remote evaluator by exactly that description, and it substitutes anyway.
#
#     Measured, and then read back to find out how. flagd answers a disabled
#     flag with reason DISABLED, no variant, and the zero value of the response
#     proto -- ResolveBoolean's `value` field is simply unset -- and
#     grpc.py:468-472 replaces that with the caller's `default_value` whenever
#     the reason is DEFAULT or DISABLED and no variant came back. So the
#     substitution is local even though the evaluation is not: what crosses the
#     wire is the signal, and the provider already holds the default.
#
#     Probed directly, each of the four flags resolves to the caller's default
#     with reason 'DISABLED', no variant and no error code. The reason arrives
#     as the server's bare string rather than the SDK's Reason enum, which the
#     scenarios do not assert and 2.2.5 does not require -- worth noting only
#     because the in-process resolver differs there, returning Reason.DISABLED.
#
#   TARGETING
#     grpc.py:492 puts the evaluation context's targeting key into the request's
#     context struct, so the server evaluates targeting-key-flag's rule against
#     it and answers `hit` or `miss`.
#
#   UNAVAILABLE_INIT
#     grpc.py:175 raises ProviderNotReadyError once the blocking init deadline
#     passes without a connection, which the SDK's registry turns into
#     PROVIDER_ERROR.
#
#   LIFECYCLE
#     Declared on a run, and the run is the point: this capability had been
#     withheld here since the first pass with nothing anywhere saying why -- the
#     @reinitialization note below treated it as given rather than justifying it
#     -- so the six lifecycle scenarios had never been put to this resolver at
#     all. Declaring it and running them settles it: all six execute, five pass,
#     and the sixth is the @reinitialization scenario dealt with below.
#
#     It is a real question here rather than a formality. An SDK synthesises
#     PROVIDER_READY around `initialize` for any provider, so the readiness
#     scenario is vacuous for one that does nothing during initialisation -- a
#     NoOpProvider passes it. This resolver blocks until the evaluation stream
#     is up and raises ProviderNotReadyError when the deadline passes
#     (grpc.py:175, grpc.py:261), so both terminal outcomes the feature file
#     asserts are outcomes this provider actually reaches.
#
#     Java, Go and JavaScript all declare it on both resolvers, and Go's
#     adoption records having made and reverted this exact mistake: withholding
#     it left that suite blind to six scenarios another language was running
#     against the same provider. Python was the last of the four still doing so.
#
#   NUMERIC_COERCION
#     Declared, and failing the lossy scenario -- deliberately, and the failure
#     is the report. See KNOWN_DEVIATIONS below.
#
#     RPC does not type-check locally: grpc.py:444-448 asks flagd for an Int and
#     passes back whatever the server answers, so the whole decision is flagd's.
#     flagd's evaluator resolves the variant as a float64 and casts it with a
#     bare `int64(val)` (core/pkg/evaluator/json.go, ResolveIntValue, at the
#     v0.16.0 the testbed's `flagd/Dockerfile` builds on), so `float-flag`'s 0.5
#     comes back as 0 with reason STATIC and no error code -- silently narrowed,
#     which is the one thing the lossy scenario forbids. Measured, not read off
#     the server source: the scenario fails with `flag 'float-flag' resolved to
#     0 (int), expected 1 (int)`.
#
#     Declared rather than withheld because this resolver *attempts* the
#     coercion and gets one direction wrong, which is the case Appendix F's
#     numeric-coercion note now names outright: a provider in that position
#     declares the capability and lets the scenario fail. That note said the
#     opposite until spec@045950ca -- withhold, and say which it is -- and two
#     of the four adoptions followed it there. `integer-flag` requested as a
#     Float passes here, so withdrawing the tag would turn a real, specific
#     defect into a skip indistinguishable from a provider that declines to
#     coerce at all, which is the failure mode the deviation field exists to
#     prevent.
#
#     **The in-process resolver passes this scenario.** It refuses 0.5 as an
#     Integer with TYPE_MISMATCH, because it evaluates locally and never asks
#     flagd. One provider, two resolvers, opposite answers -- which is why the
#     deviation below is on this suite only and is not mirrored onto that one.
#     Java and Go both attach their equivalent entry to both of their resolvers,
#     correctly, because in those languages both narrow identically; Python is
#     the language where that would be false.
#
#     Worth keeping because it was got wrong twice, in two languages, by reading
#     the source: Python's RPC resolver narrows exactly as Go's and Java's do,
#     and only its in-process resolver is the exception -- the only such resolver
#     in the four languages. The claim that this path returns INVALID_ARGUMENT
#     for a float-valued flag was made and retracted by an earlier revision of
#     this file, and asserted about Python by the Go suite until it was corrected
#     there. INVALID_ARGUMENT is what grpc.py:461-462 would map to
#     TypeMismatchError if it ever arrived; for a float-valued flag it does not.
#     A run settled it; neither reading did.
#
#     The tag's third scenario fails for a reason that is not flagd's:
#     flagd-testbed seeds no `integral-float-flag`, so it is FLAG_NOT_FOUND. The
#     conftest records it and the deviation summary disclaims it, which is the
#     shape Java uses; it is not a reason to withhold the tag.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld, and this is a change: it was declared here until this pass and
#     failed on every run. Exactly one scenario carries the tag, and it asks for
#     `huge-integer-flag`, which flagd-testbed v3.8.0 does not seed -- so the
#     declaration was a claim with no evidence behind it either way, and its
#     failure read as a provider defect while establishing nothing about the
#     provider. Nothing in this path would narrow the value: flagd holds every
#     numeric variant as a float64 and 2^53 - 1 is exactly the largest integer a
#     float64 represents without rounding, the server casts it to the int64 of
#     ResolveIntResponse.value, and grpc.py:448 hands that to the SDK as an
#     unbounded Python int. Nothing in between is 32 bits wide. The suite simply
#     cannot show that.
#
#     The rule this and NUMERIC_COERCION are both decided by is **Appendix F's
#     sixth declaring rule** -- declare when at least one scenario gating the tag
#     can actually be put to the provider, withhold only when none can, the unit
#     being the scenario and not the tag. It is cited rather than restated: the
#     wording these two suites used last pass is what went into the appendix at
#     spec@4cab0320, so the appendix is now where it lives and a copy here would
#     be a second place for it to drift. The two gaps look like the same
#     missing-fixture problem and are not. @numeric-coercion has three scenarios
#     and this backend can ask two of them -- and their answers differ between
#     the two resolvers, which is the finding a withholding would have buried.
#     @large-integers has one, and this backend can ask none of it.
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
#   REINITIALIZATION
#     New at spec@fc99d5ac, which gated the scenario "A provider that was shut
#     down can be initialized again" that had been untagged before it. Withheld,
#     and for one reason rather than the two this note used to give.
#
#     RPC genuinely does not support reuse, measured rather than reasoned about:
#     with LIFECYCLE declared the scenario runs, and it fails with `boolean-flag`
#     resolving to the code default because grpc.py:420 raises "Cannot invoke RPC
#     on closed channel!". shutdown() closes the channel and the second
#     initialize() does not rebuild it, so the provider evaluates against a
#     closed connection rather than failing outright -- exactly the shape the
#     specification's own note on this capability describes. Requirement 2.5.2
#     says a provider SHOULD revert to its uninitialized state and that "some
#     providers MAY allow reinitialization", so reuse is permitted rather than
#     required and declining it is a choice the specification offers. Hence no
#     KnownDeviation entry: there is no requirement to deviate from.
#
#     The second reason is gone, and it was the load-bearing one for the wrong
#     thing. It ran: the scenario also carries @lifecycle, neither resolver
#     declared LIFECYCLE, so declaring REINITIALIZATION alone would leave the
#     scenario skipped and the claim unexamined. True at the time, but it rested
#     on a withholding that nothing justified, and it is what kept @lifecycle
#     unexamined for six passes. LIFECYCLE is declared above now, so the
#     scenario runs and this withholding rests on the measurement alone -- which
#     is where it should always have rested. The in-process suite declares
#     REINITIALIZATION for the same reason in reverse: it runs, and it passes.
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
#     Worth recording that the DISABLED row passes despite the reason arriving as
#     flagd's bare string rather than the SDK's Reason enum, noted under
#     DISABLED_FLAGS above: the step compares the reason as text, and "DISABLED"
#     is "DISABLED" either way. The in-process resolver returns Reason.DISABLED
#     and passes identically.
#
#   CACHING
#     Reserved in the Capability enum; no scenario carries the tag. Declaring a
#     capability nothing exercises would be a claim with no evidence behind it,
#     so it is left out of both suites. @targeting was reserved alongside it
#     until spec@26362f85 gave it three scenarios, and is now declared above.
RPC_CAPABILITIES = frozenset(
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
    }
)

KNOWN_DEVIATIONS = (
    KnownDeviation.tracked(
        capability=Capability.NUMERIC_COERCION,
        issue="https://github.com/open-feature/flagd/issues/1996",
        summary=(
            "The lossy half of the coercion rule is not enforced: evaluating "
            "float-flag (0.5) through the integer accessor returns 0 with no "
            "error code, rather than TYPE_MISMATCH with the code default, so "
            "the fractional part is discarded silently. Lossless coercion is "
            "permitted and is not the defect -- this resolver does widen an "
            "integer to a float correctly, which is why the capability is "
            "declared and the scenario left to fail rather than the capability "
            "withheld. The rule is flagd's own accepted numeric-coercion ADR "
            "rather than a specification requirement, which does not define "
            "numeric coercion at all (open-feature/spec#430), so this is a "
            "deviation from a commitment flagd made rather than from the "
            "provider contract. Unlike the Java and Go flagd providers, whose "
            "two resolvers narrow identically and which therefore place the "
            "defect in their shared provider layer, this one is in the server "
            "alone: the Python in-process resolver evaluates locally and "
            "refuses 0.5 as an integer correctly, so it is not recorded as "
            "deviating and carries no equivalent entry. The "
            "tag's third scenario also fails, but for an unrelated reason that "
            "is not flagd's: integral-float-flag is absent from the pinned "
            "flagd-testbed image, open-feature/flagd-testbed#392."
        ),
    ),
)
"""The one requirement this resolver is known to fail.

Takes the **declared and failing** shape rather than the withheld-and-skipped
one, which is the shape Appendix F's guidance prefers and this is the case it
prefers it for: flagd does attempt the coercion -- the widening scenario passes
-- and gets the narrowing direction wrong, so withdrawing the capability would
turn a real failure into a skip indistinguishable from a provider that declines
to coerce. The failure stays visible in the results and this entry says it is
known and why.

Recorded against this resolver only. See the in-process suite, which passes the
scenario this deviates on.
"""

RPC_SUITE = ResolverSuite(
    name="flagd-rpc",
    resolver_type=ResolverType.RPC,
    backend_port=RPC_PORT,
    capabilities=RPC_CAPABILITIES,
    known_deviations=KNOWN_DEVIATIONS,
    # RPC holds no ruleset of its own: it is ready as soon as the evaluation
    # stream is up, so it needs less headroom than in-process.
    ready_timeout=30.0,
)


@pytest.fixture(scope="session")
def tck_config(tck_backend: RunningBackend, closed_port: int) -> TckConfig:
    """The whole of this adoption's wiring.

    ``tck_backend`` is the TCK's own session-scoped fixture: it has already
    started the Compose file ``tests/tck/conftest.py`` declares, discovered the
    dynamically mapped host ports, built the control against the launchpad and
    waited for it to accept commands.
    """
    return build_config(RPC_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
