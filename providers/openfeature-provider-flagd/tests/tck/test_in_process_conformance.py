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
#   STRICT_NUMERIC_TYPING
#     Local, and strict: flagd_core.py:25 admits only `int` for an integer
#     request, and flagd_core.py:228-231 raises TypeMismatchError for anything
#     else -- so `float-flag`'s 0.5 is reported as a mismatch rather than
#     narrowed to 0. (The float mapping at flagd_core.py:26 is deliberately the
#     wider one, `(int, float)`, but widening towards float loses nothing.)
#
# Not declared, and why:
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
        Capability.STRICT_NUMERIC_TYPING,
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
