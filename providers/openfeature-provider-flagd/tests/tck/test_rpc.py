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

# Every capability below was declared, the suite run, and its scenarios seen to
# pass. The code references say where the behaviour lives, so a reader can check
# the claim.
#
#   EVENTS      grpc.py:261 emits PROVIDER_READY when the evaluation stream
#               delivers its 'provider_ready' message.
#   STALE       grpc.py:202-212 goes STALE on TRANSIENT_FAILURE and only then
#               starts the timer escalating to ERROR.
#   CONFIGURATION_CHANGE
#               grpc.py:302 names the changed keys, and grpc.py:298-300 evicts
#               exactly those from the LRU cache -- so the re-evaluation the
#               scenario performs cannot be served a stale cached value.
#   OBJECT      grpc.py:336, through ResolveObject.
#   VARIANTS    grpc.py:449 carries the response's `variant` into the details.
#               Seven of the outline's eight rows pass; the eighth asks for a
#               flag the backend does not seed.
#   TARGETING   grpc.py:492 puts the targeting key into the request's context
#               struct, so the server evaluates the rule against it.
#   UNAVAILABLE_INIT
#               grpc.py:175 raises ProviderNotReadyError once the blocking init
#               deadline passes without a connection.
#   DISABLED_FLAGS
#               All four rows pass, which is not obvious for a remote evaluator:
#               flagd sends reason DISABLED, no variant and the proto's zero
#               value, and grpc.py:468-472 substitutes the caller's
#               `default_value` locally. What crosses the wire is the signal.
#   LIFECYCLE   Not a formality: this resolver blocks until the evaluation stream
#               is up and raises ProviderNotReadyError when the deadline passes
#               (grpc.py:175, grpc.py:261), so both terminal outcomes are
#               reachable. Five of six pass; the sixth is @reinitialization,
#               below.
#   STANDARD_REASONS
#               All nine scenarios pass; the last three also need @targeting and
#               @disabled-flags, both declared here. The DISABLED row passes
#               despite the reason arriving as flagd's bare string rather than
#               the SDK's Reason enum, because the step compares it as text.
#
#   NUMERIC_COERCION
#     Declared, and failing the lossy scenario deliberately -- the failure is the
#     report; see KNOWN_DEVIATIONS below. RPC does not type-check locally:
#     grpc.py:444-448 asks flagd for an Int and passes back whatever the server
#     answers, and flagd's evaluator casts the float64 variant with a bare
#     `int64(val)` (core/pkg/evaluator/json.go, ResolveIntValue), so
#     `float-flag`'s 0.5 comes back as 0 with no error code.
#
#     **The in-process resolver passes that scenario**, refusing 0.5 as an
#     Integer, which is why the deviation is on this suite only and why the tag
#     is declared and left to fail rather than withheld: a skip cannot say "it
#     coerces, and one direction is wrong" (python-sdk-contrib#420). The tag's
#     third scenario fails for a reason that is not flagd's: flagd-testbed seeds
#     no `integral-float-flag`.
#
#   STRING_TYPING and FULLY_TYPED_VALUES
#     Both declared, on a run. The decision is flagd's for the same reason the
#     coercion one is -- grpc.py asks the server for a String and hands back
#     what it answers -- and flagd holds a ruleset rather than a string table,
#     typing every variant out of the JSON, so a bool, a number or a structure
#     reached through ResolveString is a TYPE_MISMATCH the server raises. That
#     is not a property of flagd that could be read off this repository at all,
#     which is why both tags rest on a run rather than on an argument.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld: the tag's one scenario asks for `huge-integer-flag` and no
#     released flagd-testbed seeds it, so none of its scenarios reach this
#     provider. Nothing in this path would narrow the value -- flagd holds every
#     numeric variant as a float64, 2^53 - 1 is exactly the largest integer a
#     float64 represents without rounding, and grpc.py:448 hands
#     ResolveIntResponse.value to the SDK as an unbounded Python int -- and the
#     suite cannot show that, which is the point. No KnownDeviation: the gap is
#     the backend's. Declare the tag once open-feature/flagd-testbed#392 is in
#     the image, or the withholding starts reading as a claim about the provider.
#
#   REINITIALIZATION
#     Withheld, on the measurement: with LIFECYCLE declared the scenario runs
#     and fails, because grpc.py:420 raises "Cannot invoke RPC on closed
#     channel!" -- shutdown() closes the channel and the second initialize()
#     does not rebuild it. No KnownDeviation: requirement 2.5.2 permits reuse
#     rather than requiring it. The in-process suite declares it for the same
#     reason in reverse -- it runs, and it passes.
#
#   CACHING
#     No scenario carries the tag.
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
        Capability.STRING_TYPING,
        Capability.FULLY_TYPED_VALUES,
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
            "withheld. The defect is in flagd itself rather than in this "
            "provider layer: the Python in-process resolver evaluates locally "
            "and refuses 0.5 as an integer correctly, so it is not recorded as "
            "deviating and carries no equivalent entry. The tag's third "
            "scenario also fails, but for an unrelated reason that is not "
            "flagd's: integral-float-flag is absent from the pinned "
            "flagd-testbed image, open-feature/flagd-testbed#392."
        ),
    ),
)
"""The one requirement this resolver is known to fail; the in-process suite passes it."""

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
    """The whole of this adoption's wiring."""
    return build_config(RPC_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
