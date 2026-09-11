"""The OpenFeature provider conformance suite, run against flagd's RPC resolver.

RPC asks flagd to evaluate each flag over gRPC and maps the response onto typed
resolution details, so what is under test here is that mapping plus the
lifecycle the evaluation stream drives.
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
#     which is the one thing the lossy scenario forbids. The two lossless
#     scenarios pass for the same reason: 10.0 casts to 10, and a float
#     accessor sees the float64 the server already holds. One of three is a
#     failure, and a declaration is all or nothing.
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
#     declaration of the kind the reserved tags below are kept out for.
#
#     Worth recording that this scenario never ran here, at this pin or the one
#     before it: it is one of the six @lifecycle skips each resolver reports,
#     not a scenario that used to pass. Reading its absence from the failure
#     list as evidence of support is the mistake this note exists to prevent.
#
#   TARGETING, CACHING
#     Reserved in the Capability enum; no scenario carries either tag. Declaring
#     a capability nothing exercises would be a claim with no evidence behind it,
#     so they are left out of both suites.
RPC_CAPABILITIES = frozenset(
    {
        Capability.EVENTS,
        Capability.STALE,
        Capability.CONFIGURATION_CHANGE,
        Capability.OBJECT,
        Capability.UNAVAILABLE_INIT,
        Capability.LARGE_INTEGERS,
    }
)

RPC_SUITE = ResolverSuite(
    name="flagd-rpc",
    resolver_type=ResolverType.RPC,
    capabilities=RPC_CAPABILITIES,
    # RPC holds no ruleset of its own: it is ready as soon as the evaluation
    # stream is up, so it needs less headroom than in-process.
    ready_timeout=30.0,
)


@pytest.fixture(scope="session")
def tck_config(
    flagd_testbed: FlagdContainer,
    flagd_control: HttpControl,
    closed_port: int,
) -> TckConfig:
    return build_config(RPC_SUITE, flagd_testbed, flagd_control, closed_port)


scenarios(features_path())
