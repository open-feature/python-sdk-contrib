"""Shared wiring for the two flagd conformance suites.

flagd resolves flags two quite different ways -- RPC evaluates remotely over
gRPC, in-process syncs the ruleset and evaluates locally -- and they are separate
suites because they are separately conformant. Any difference between the two
results is a difference an application would see when it switches resolver,
which is exactly the class of thing the conformance suite exists to surface.

Everything they share lives here; everything that differs lives in the two
``test_*_conformance`` modules next to it, where a reader can see the whole of a
resolver's declaration in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.contrib.tools.provider_tck import (
    Capability,
    HttpControl,
    TckConfig,
)
from openfeature.provider import FeatureProvider
from tests.e2e.flagd_container import FlagdContainer

__all__ = ["ResolverSuite", "build_config"]

# Timings. flagd exposes several and they interact, so they are named here once
# rather than scattered through two suites.

DEADLINE_MS = 5000
"""How long a provider blocks during initialisation before giving up.

This, and not ``TckConfig.ready_timeout``, is what actually bounds flagd's
initialisation: the resolvers block inside ``initialize`` and raise
``ProviderNotReadyError`` when it expires (grpc.py:175, grpc_watcher.py:151).
Generous because every scenario is preceded by a control-API ``/start``, which
restarts the flagd process -- so a provider is routinely built against a backend
that came up milliseconds ago.

For the RPC resolver it also bounds each individual resolution call.
"""

RETRY_BACKOFF_MS = 500
"""Initial delay before a reconnect attempt. Short, so an ended outage is noticed quickly."""

RETRY_BACKOFF_MAX_MS = 5000
"""Longest delay between reconnect attempts, and the wait between stream retries.

Kept at or above :data:`DEADLINE_MS`: the provider passes the deadline to gRPC as
``grpc.min_reconnect_backoff_ms`` and this as ``grpc.max_reconnect_backoff_ms``
(grpc.py:90-92), so a smaller value here would be a channel configured with a
minimum backoff above its maximum.
"""

RETRY_GRACE_PERIOD_SECONDS = 30
"""How long a disconnected provider stays STALE before escalating to ERROR.

Load-bearing for the ``@stale`` scenario. Both resolvers go STALE the moment the
channel fails and start a timer that escalates to ERROR when this expires
(grpc.py:204-210, grpc_watcher.py:180-186). Too short a value turns a scenario
about staleness into one about failure, because the outage lasts as long as the
scenario needs to observe it.
"""

STREAM_DEADLINE_MS = 0
"""Disable periodic stream recycling, as the existing e2e suites do.

A recycle is invisible to the provider contract, but disabling it removes a
source of background reconnects from a suite whose whole subject is what a
reconnect looks like.
"""

UNAVAILABLE_DEADLINE_MS = 500
UNAVAILABLE_GRACE_PERIOD_SECONDS = 1
UNAVAILABLE_BACKOFF_MS = 5000
"""Deliberately impatient settings for the provider that cannot reach a backend.

The ``@unavailable`` scenarios assert that failure is reported *promptly*, so a
provider taking 30 seconds to give up would pass a test about eventual failure
while failing the one that matters. The backoff is long for the opposite reason:
after the error is reported, the next failed reconnect attempt would emit
another ``PROVIDER_STALE`` and move the provider out of the ERROR state the
scenario is about to assert.
"""

EVENT_TIMEOUT = 20.0
"""Seconds to wait for a provider event.

Comfortably above :data:`RETRY_BACKOFF_MAX_MS`, which is how long a provider may
wait before the reconnect attempt that produces the ``PROVIDER_READY`` ending
the ``@stale`` scenario.
"""


@dataclass(frozen=True)
class ResolverSuite:
    """What differs between the two resolvers' suites."""

    name: str
    """Names the suite in test output and scopes its OpenFeature domain."""

    resolver_type: ResolverType

    capabilities: frozenset[Capability]
    """Derived from reading the resolver's event emission, not from running the suite.

    See each suite module for the evidence behind every entry, and behind every
    omission.
    """

    ready_timeout: float


def build_config(
    suite: ResolverSuite,
    container: FlagdContainer,
    control: HttpControl,
    closed_port: int,
) -> TckConfig:
    """Wire one resolver up to the running testbed.

    The ports are read here, after the stack is up: the testbed maps host ports
    dynamically, so they do not exist earlier -- and they stay valid for the
    whole session because nothing ever restarts a container. Outages are
    simulated inside the running stack through ``control`` instead.
    """
    port = container.get_port(suite.resolver_type)

    def new_provider() -> FeatureProvider:
        return FlagdProvider(
            resolver_type=suite.resolver_type,
            host="localhost",
            port=port,
            deadline_ms=DEADLINE_MS,
            stream_deadline_ms=STREAM_DEADLINE_MS,
            retry_backoff_ms=RETRY_BACKOFF_MS,
            retry_backoff_max_ms=RETRY_BACKOFF_MAX_MS,
            retry_grace_period=RETRY_GRACE_PERIOD_SECONDS,
        )

    def new_unavailable_provider() -> FeatureProvider:
        # Pointed at a closed port on localhost, never at the backend under
        # test: that has to stay up, and simulated outages belong to the control
        # API.
        return FlagdProvider(
            resolver_type=suite.resolver_type,
            host="localhost",
            port=closed_port,
            deadline_ms=UNAVAILABLE_DEADLINE_MS,
            stream_deadline_ms=STREAM_DEADLINE_MS,
            retry_backoff_ms=UNAVAILABLE_BACKOFF_MS,
            retry_backoff_max_ms=UNAVAILABLE_BACKOFF_MS,
            retry_grace_period=UNAVAILABLE_GRACE_PERIOD_SECONDS,
        )

    return TckConfig(
        name=suite.name,
        control=control,
        new_provider=new_provider,
        new_unavailable_provider=new_unavailable_provider,
        capabilities=suite.capabilities,
        event_timeout=EVENT_TIMEOUT,
        ready_timeout=suite.ready_timeout,
    )
