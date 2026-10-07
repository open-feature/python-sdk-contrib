"""The OpenFeature provider conformance suite, run against flagd's in-process resolver.

In-process syncs the whole ruleset over flagd's sync API and evaluates locally,
so unlike RPC the type-checking, the variant selection and the reason all come
from ``openfeature-flagd-core`` in this process rather than from the server --
which is why this is a separate suite rather than a parametrisation of the RPC
one.
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

# Every capability below was declared, the suite run, and its scenarios seen to
# pass. The code references say where the behaviour lives, so a reader can check
# the claim.
#
#   EVENTS      grpc_watcher.py:262 emits PROVIDER_READY only once the first sync
#               payload has been *applied* (grpc_watcher.py:254), so a scenario
#               evaluating straight after ready cannot race the sync.
#   STALE       grpc_watcher.py:178-190 goes STALE on TRANSIENT_FAILURE and only
#               then starts the timer escalating to ERROR.
#   CONFIGURATION_CHANGE
#               in_process.py:34 names exactly the keys FlagdCore reports as
#               changed.
#   OBJECT      in_process.py:122.
#   VARIANTS    flagd_core.py returns the selected variant with every resolution;
#               in_process.py carries it into the details.
#   TARGETING   targeting.py:40-41 puts the targeting key into the JSON-logic
#               context; flagd_core.py:154 evaluates the rule against it.
#   UNAVAILABLE_INIT
#               grpc_watcher.py:151 raises ProviderNotReadyError once the
#               blocking init deadline passes without a synced ruleset.
#   DISABLED_FLAGS
#               flagd_core.py:143-145 returns the caller's `default_value` with
#               reason DISABLED before targeting or variant selection, and
#               flagd_core.py:199-200 then skips the type check for that reason
#               -- which is what stops the substituted default being re-typed
#               against the flag it did not come from.
#   LIFECYCLE   Not a formality: this resolver applies the entire ruleset before
#               ready (grpc_watcher.py:254-262) and initialisation can fail
#               (grpc_watcher.py:151), so both terminal outcomes are reachable.
#   STANDARD_REASONS
#               All nine scenarios pass; the last three also need @targeting and
#               @disabled-flags, both declared here.
#   REINITIALIZATION
#               Withheld on RPC, declared here on the same run: this resolver
#               restarts serving `boolean-flag` correctly where RPC evaluates
#               against a closed channel.
#
#   NUMERIC_COERCION
#     Declared on RPC too, but not the same claim: **this resolver satisfies the
#     lossy half and RPC does not.** Evaluation is local, so flagd_core.py:25
#     admits only `int` for an integer request and `_check_type`
#     (flagd_core.py:228-231) raises TypeMismatchError for anything else, while
#     the float mapping at flagd_core.py:26 is the wider `(int, float)`. No
#     KnownDeviation here, and RPC's entry is deliberately not mirrored onto
#     this suite (open-feature/python-sdk-contrib#420). The tag's third scenario
#     fails for a reason that is not about coercion: flagd-testbed seeds no
#     `integral-float-flag`.
#
#   STRING_TYPING and FULLY_TYPED_VALUES
#     Both declared, on a run. `_TYPE_MAP`'s string entry is the narrow `(str,)`
#     (flagd_core.py:23) and `_check_type` (flagd_core.py:228-231) raises
#     TypeMismatchError for anything else, so nothing renders a bool, a number
#     or a structure as text -- the one accessor `bool` does not slip through,
#     because `str` is not in bool's ancestry. The ruleset is `json.loads`
#     output all the way down (flagd_core.py:73), so there is no type this
#     resolver keeps as text and the second tag has an answer here too.
#
# Not declared, and why:
#
#   LARGE_INTEGERS
#     Withheld: the tag's one scenario asks for `huge-integer-flag` and no
#     released flagd-testbed seeds it, so none of its scenarios reach this
#     provider. No KnownDeviation -- the gap is the backend's. Declare the tag
#     once open-feature/flagd-testbed#392 is in the image, or the withholding
#     starts reading as a claim about the provider.
#
#   CACHING
#     No scenario carries the tag.
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
        Capability.STRING_TYPING,
        Capability.FULLY_TYPED_VALUES,
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
    """The whole of this adoption's wiring."""
    return build_config(IN_PROCESS_SUITE, tck_backend, closed_port)


scenarios(*feature_paths())
