"""Shared wiring for the two flagd conformance suites.

flagd resolves flags two quite different ways -- RPC evaluates remotely over
gRPC, in-process syncs the ruleset and evaluates locally -- and they are
separate suites because they are separately conformant. What is shared is the
timings, which are flagd's own and interact, and the one function that turns a
resolver plus a running endpoint into a ``TckConfig``; what differs lives in
``test_rpc.py`` and ``test_in_process.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.contrib.tools.tck import (
    Capability,
    KnownDeviation,
    RunningBackend,
    TckConfig,
)
from openfeature.provider import FeatureProvider

__all__ = ["IN_PROCESS_PORT", "RPC_PORT", "ResolverSuite", "build_config"]

RPC_PORT = 8013
IN_PROCESS_PORT = 8015
"""Container-internal ports flagd serves remote evaluation and the sync stream on.

Named here rather than in ``conftest.py`` so that the declaration and the
resolver that uses it cannot drift apart.
"""

DEADLINE_MS = 5000
"""How long a provider blocks during initialisation before giving up.

This, and not ``TckConfig.ready_timeout``, is what actually bounds flagd's
initialisation: the resolvers block inside ``initialize`` and raise
``ProviderNotReadyError`` when it expires (grpc.py:175, grpc_watcher.py:151).
Generous because every scenario is preceded by a control-API ``/start``, so a
provider is routinely built against a backend that came up milliseconds ago.

For the RPC resolver it also bounds each individual resolution call.
"""

RETRY_BACKOFF_MS = 500
"""Initial delay before a reconnect attempt. Short, so an ended outage is noticed quickly."""

RETRY_BACKOFF_MAX_MS = 5000
"""Longest delay between reconnect attempts, and the wait between stream retries.

Kept at or above :data:`DEADLINE_MS`: the provider passes the deadline to gRPC
as ``grpc.min_reconnect_backoff_ms`` and this as
``grpc.max_reconnect_backoff_ms`` (grpc.py:90-92), so a smaller value here would
be a channel configured with a minimum backoff above its maximum.
"""

RETRY_GRACE_PERIOD_SECONDS = 30
"""How long a disconnected provider stays STALE before escalating to ERROR.

Load-bearing for the ``@stale`` scenario: both resolvers start the escalation
timer the moment the channel fails (grpc.py:204-210, grpc_watcher.py:180-186),
so too short a value turns a scenario about staleness into one about failure.
"""

STREAM_DEADLINE_MS = 0
"""Disable periodic stream recycling, as the existing e2e suites do.

It removes a source of background reconnects from a suite whose whole subject
is what a reconnect looks like.
"""

UNAVAILABLE_DEADLINE_MS = 500
UNAVAILABLE_GRACE_PERIOD_SECONDS = 1
UNAVAILABLE_BACKOFF_MS = 5000
"""Deliberately impatient settings for the provider that cannot reach a backend.

The ``@unavailable`` scenarios assert that failure is reported *promptly*, so a
provider taking 30 seconds to give up would pass a test about eventual failure
while failing the one that matters. The backoff is long for the opposite
reason: after the error is reported, the next failed reconnect attempt would
emit another ``PROVIDER_STALE`` and move the provider out of the ERROR state the
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

    backend_port: int
    """Container-internal port, resolved to a host port once the stack is up."""

    capabilities: frozenset[Capability]
    """What this resolver was run against the suite and seen to satisfy.

    See each suite module for the evidence behind every entry and omission.
    """

    ready_timeout: float

    known_deviations: tuple[KnownDeviation, ...] = ()
    """Requirements this resolver is known to fail, acknowledged rather than hidden.

    **Per resolver, and that is the whole reason this field is here rather than
    shared.** RPC narrows ``float-flag`` to ``0`` where in-process refuses it,
    so an entry naming :attr:`~Capability.NUMERIC_COERCION` is true of one and
    false of the other, and attaching it to both would publish a defect against
    the resolver that does not have it.
    """


def build_config(
    suite: ResolverSuite,
    backend: RunningBackend,
    closed_port: int,
) -> TckConfig:
    """Wire one resolver up to the running testbed.

    A factory because the mapped host port does not exist until the stack is up.
    The host comes from the endpoint rather than being written as
    ``"localhost"``, because with a remote Docker daemon, Docker Desktop on some
    platforms or a rootless setup it is neither localhost nor predictable.
    """
    endpoint = backend.endpoint

    def new_provider() -> FeatureProvider:
        return FlagdProvider(
            resolver_type=suite.resolver_type,
            host=endpoint.host,
            port=endpoint.port(suite.backend_port),
            deadline_ms=DEADLINE_MS,
            stream_deadline_ms=STREAM_DEADLINE_MS,
            retry_backoff_ms=RETRY_BACKOFF_MS,
            retry_backoff_max_ms=RETRY_BACKOFF_MAX_MS,
            retry_grace_period=RETRY_GRACE_PERIOD_SECONDS,
        )

    def new_unavailable_provider() -> FeatureProvider:
        # A closed port on localhost, never the backend under test: that has to
        # stay up for every other scenario.
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
        control=backend.control,
        new_provider=new_provider,
        new_unavailable_provider=new_unavailable_provider,
        capabilities=suite.capabilities,
        known_deviations=suite.known_deviations,
        event_timeout=EVENT_TIMEOUT,
        ready_timeout=suite.ready_timeout,
    )
