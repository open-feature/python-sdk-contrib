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
#   STRICT_NUMERIC_TYPING
#     RPC does not type-check locally; it asks flagd for an Int and flagd answers
#     INVALID_ARGUMENT for a float-valued flag, which grpc.py:461-462 maps to
#     TypeMismatchError. So 0.5 is never narrowed to 0.
#
# Not declared, and why:
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
        Capability.STRICT_NUMERIC_TYPING,
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
