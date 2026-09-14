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
# pass. The code references say where the behaviour lives, so that a reader can
# check the claim -- the run is what it rests on, which is Appendix F's rule and
# not a preference here. @reinitialization is the case in point: this resolver's
# shutdown reverts enough of its own state to read as support for reuse, and the
# channel underneath cannot be rebuilt.
#
#   EVENTS      grpc.py:261 emits PROVIDER_READY when the evaluation stream
#               delivers its 'provider_ready' message.
#   STALE       grpc.py:202-212 emits PROVIDER_STALE on TRANSIENT_FAILURE and
#               only then starts the timer escalating to PROVIDER_ERROR once
#               retry_grace_period expires.
#   CONFIGURATION_CHANGE
#               grpc.py:302 emits PROVIDER_CONFIGURATION_CHANGED with the changed
#               keys, and grpc.py:298-300 evicts exactly those keys from the LRU
#               cache -- so the re-evaluation the scenario performs afterwards
#               cannot be served a stale cached value.
#   OBJECT      grpc.py:336 resolves structured values through ResolveObject.
#   VARIANTS    grpc.py:449 carries the response's `variant` into the resolution
#               details for every typed call. Seven of the outline's eight rows
#               pass; the eighth asks for a flag the backend does not seed.
#   TARGETING   grpc.py:492 puts the evaluation context's targeting key into the
#               request's context struct, so the server evaluates
#               targeting-key-flag's rule against it and answers hit or miss.
#   UNAVAILABLE_INIT
#               grpc.py:175 raises ProviderNotReadyError once the blocking init
#               deadline passes without a connection, which the SDK's registry
#               turns into PROVIDER_ERROR.
#
#   DISABLED_FLAGS
#     All four rows pass, and the measurement is worth keeping because a remote
#     evaluator satisfying this is not obvious. flagd answers a disabled flag
#     with reason DISABLED, no variant, and the zero value of the response proto
#     -- ResolveBoolean's `value` field is simply unset -- and grpc.py:468-472
#     replaces that with the caller's `default_value` whenever the reason is
#     DEFAULT or DISABLED and no variant came back. So the substitution is local
#     even though the evaluation is not: what crosses the wire is the signal, and
#     the provider already holds the default.
#
#     Probed directly, each of the four flags resolves to the caller's default
#     with reason 'DISABLED', no variant and no error code. The reason arrives as
#     the server's bare string rather than the SDK's Reason enum, which nothing
#     asserts -- noted only because the in-process resolver differs, returning
#     Reason.DISABLED.
#
#   LIFECYCLE
#     All six scenarios execute, five pass, and the sixth is the
#     @reinitialization one dealt with below.
#
#     It is a real question here rather than a formality, which is the test the
#     capability's own documentation sets: an SDK synthesises PROVIDER_READY
#     around `initialize` for any provider, so the readiness scenario is vacuous
#     for one that does nothing during initialisation. This resolver blocks until
#     the evaluation stream is up and raises ProviderNotReadyError when the
#     deadline passes (grpc.py:175, grpc.py:261), so both terminal outcomes the
#     feature file asserts are outcomes this provider actually reaches.
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
#     **The in-process resolver passes that scenario.** It refuses 0.5 as an
#     Integer with TYPE_MISMATCH, because it evaluates locally and never asks
#     flagd, while `integer-flag` requested as a Float widens correctly on both.
#     One provider, two resolvers, opposite answers to the question this
#     capability exists to ask -- which is why the deviation below is on this
#     suite only and is deliberately not mirrored onto that one, and why the tag
#     is declared and left to fail rather than withheld: a skip cannot say "it
#     coerces, and one direction is wrong". Filed as
#     open-feature/python-sdk-contrib#420.
#
#     The tag's third scenario fails for a reason that is not flagd's:
#     flagd-testbed seeds no `integral-float-flag`, so it is FLAG_NOT_FOUND. The
#     conftest records it and the deviation summary disclaims it; it is not a
#     reason to withhold the tag.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld. Exactly one scenario carries the tag, it asks for
#     `huge-integer-flag`, and no released flagd-testbed seeds such a flag -- so this
#     backend can put none of the tag's scenarios to this provider, and Appendix
#     F's sixth declaring rule says withhold. Nothing in this path would narrow
#     the value: flagd holds every numeric variant as a float64 and 2^53 - 1 is
#     exactly the largest integer a float64 represents without rounding, the
#     server casts it to the int64 of ResolveIntResponse.value, and grpc.py:448
#     hands that to the SDK as an unbounded Python int. Nothing in between is 32
#     bits wide -- and the suite cannot show that, which is the point.
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
#   REINITIALIZATION
#     Withheld, on the measurement: with LIFECYCLE declared the scenario runs,
#     and it fails with `boolean-flag` resolving to the code default because
#     grpc.py:420 raises "Cannot invoke RPC on closed channel!". shutdown()
#     closes the channel and the second initialize() does not rebuild it, so the
#     provider evaluates against a closed connection rather than failing
#     outright. Requirement 2.5.2 permits reuse rather than requiring it, so this
#     is a choice the specification offers and there is no requirement to deviate
#     from: no KnownDeviation. The in-process suite declares it for the same
#     reason in reverse -- it runs, and it passes.
#
#   STANDARD_REASONS
#     Declared on a run rather than on the source. All nine scenarios pass -- the
#     four rule-less rows as STATIC, an unknown flag and a type mismatch as ERROR
#     beside their error codes, TARGETING_MATCH for the matched rule and DEFAULT
#     for the miss, DISABLED for a disabled flag. The last three need @targeting
#     and @disabled-flags as well, which this suite declares, so none of the file
#     is skipped here.
#
#     The DISABLED row passes despite the reason arriving as flagd's bare string
#     rather than the SDK's Reason enum: the step compares the reason as text.
#
#   CACHING
#     Reserved, and the harness refuses it: no scenario carries the tag.
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

Declared-and-failing rather than withheld-and-skipped, and recorded against this
resolver only: the in-process suite passes the scenario this deviates on.
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

    ``tck_backend`` is the TCK's own session-scoped fixture: the stack is up and
    its control is ready by the time this runs.
    """
    return build_config(RPC_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
