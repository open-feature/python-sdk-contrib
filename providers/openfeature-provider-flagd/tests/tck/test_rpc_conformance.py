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
#   LARGE_INTEGERS
#     RPC never narrows an integer. flagd holds every numeric variant as a
#     float64 -- Go's encoding/json decodes an untyped number into one -- and
#     2^53 - 1 is exactly the largest integer a float64 represents without
#     rounding, which is why the canonical set asks for nothing larger. The
#     server casts it to the int64 of ResolveIntResponse.value, and grpc.py:448
#     hands that to the SDK as a Python int, unbounded. Nothing in between is
#     32 bits wide.
#
# Not declared, and why:
#
#   NUMERIC_COERCION
#     RPC does not type-check locally: grpc.py:444-448 asks flagd for an Int and
#     passes back whatever the server answers, so the whole decision is flagd's.
#     flagd's evaluator resolves the variant as a float64 and casts it with a
#     bare `int64(val)` (core/pkg/evaluator/json.go, ResolveIntValue, at the
#     v0.16.0 the testbed's `flagd/Dockerfile` builds on), so `float-flag`'s 0.5
#     comes back as 0 with reason STATIC and no error code -- silently narrowed,
#     which is the one thing the lossy scenario forbids.
#
#     Measured by declaring the tag and running it, rather than read off the
#     server source: `integer-flag` requested as a Float passes, because a float
#     accessor sees the float64 the server already holds. `integral-float-flag`
#     requested as an Integer does not, and not for a reason about coercion at
#     all -- flagd-testbed seeds no such flag, so it is FLAG_NOT_FOUND, the same
#     gap the conftest records for `large-integer-flag`. So two of three fail
#     today, one on the narrowing and one on the missing flag, and what the
#     server would answer for a seeded 10.0 is unmeasured. A declaration is all
#     or nothing either way.
#
#     An earlier revision of this file claimed flagd answers INVALID_ARGUMENT
#     here. The server source says otherwise: INVALID_ARGUMENT is what
#     grpc.py:461-462 would map to TypeMismatchError if it ever arrived, and
#     for a float-valued flag it does not. The Java reference adoption recorded
#     the same narrowing against the same server. flagd's numeric-coercion ADR
#     (docs/architecture-decisions/numeric-coercion.md) commits it to lossless
#     coercion, tracked as open-feature/flagd#1996; this is declared again once
#     the testbed ships a flagd that implements it.
#
#   REINITIALIZATION
#     New at spec@fc99d5ac, which gated the scenario "A provider that was shut
#     down can be initialized again" that had been untagged before it. Withheld
#     for two independent reasons, either of which is sufficient.
#
#     First, RPC genuinely does not support reuse, which was measured rather
#     than reasoned about: declaring LIFECYCLE and REINITIALIZATION together
#     locally makes the scenario run, and it fails with `boolean-flag` resolving
#     to the code default because grpc.py:420 raises "Cannot invoke RPC on
#     closed channel!". shutdown() closes the channel and the second initialize()
#     does not rebuild it, so the provider evaluates against a closed connection
#     rather than failing outright -- exactly the shape the specification's own
#     note on this capability describes. Requirement 2.5.2 says a provider
#     SHOULD revert to its uninitialized state and that "some providers MAY
#     allow reinitialization", so reuse is permitted rather than required and
#     declining it is a choice the specification offers. Hence no
#     KnownDeviation entry: there is no requirement to deviate from.
#
#     Second, and why this cannot be declared even where reuse does work: the
#     scenario lives in lifecycle.feature, which carries @lifecycle at the
#     feature level, so it inherits that tag and carries both. The gate skips a
#     scenario when any capability gating it is undeclared, and neither resolver
#     declares LIFECYCLE. Declaring REINITIALIZATION alone would leave the
#     scenario skipped on @lifecycle and the claim unexamined -- a vacuous
#     declaration of the kind the reserved tag below is kept out for.
#
#     Worth recording that this scenario never ran here, at this pin or the one
#     before it: it is one of the six @lifecycle skips each resolver reports,
#     not a scenario that used to pass. Reading its absence from the failure
#     list as evidence of support is the mistake this note exists to prevent.
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
        Capability.LARGE_INTEGERS,
        Capability.STANDARD_REASONS,
    }
)

RPC_SUITE = ResolverSuite(
    name="flagd-rpc",
    resolver_type=ResolverType.RPC,
    backend_port=RPC_PORT,
    capabilities=RPC_CAPABILITIES,
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
