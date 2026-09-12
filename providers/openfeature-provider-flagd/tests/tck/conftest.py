"""One testbed stack, declared rather than wired, and shared by both suites.

The whole of the container lifecycle belongs to the TCK now: it starts the
Compose file once per session, discovers the dynamically mapped host ports,
builds the ``HttpControl`` against the launchpad and waits until it accepts
commands, and tears the stack down after the last scenario. What is left here is
the declaration -- which Compose file, which ports the provider connects to --
and one free port for the scenarios that need a backend that is not there.

The stack is started once per session and **never restarted** -- container
orchestrators assign host ports dynamically and cannot reliably preserve them
across a restart, so a restarted backend comes back on a different host port,
silently invalidating every provider already pointed at the old one, and the
failure looks like a flaky provider rather than a broken test. Scenario isolation
and every simulated outage go through the control API instead.

One stack for both suites because one flagd process serves both ports the
resolvers use -- 8013 for RPC and 8015 for sync -- so there is nothing a second
stack would isolate. One ``HttpControl`` with it, which matters and is not merely
tidy: the control tracks whether a disconnect has left the backend down so the
next scenario starts it rather than merely resetting flag state, and two
instances would each hold half of that knowledge. A session-scoped
``tck_backend`` is what makes both true by construction.

The launchpad registers only ``/start``, ``/restart``, ``/stop`` and ``/change``
(flagd-testbed ``launchpad/main.go``), so ``/reset`` answers 404 and every
``prepare_scenario`` takes the documented ``/start`` fallback. The probe costs
one 404 for the whole session. It serves no ``/healthz`` either, which the
control API document defines as ready -- so the readiness wait rests on the
control port accepting a connection, which the harness establishes before it
probes.

**The testbed does not yet serve the whole canonical flag set.** The conformance
assets at spec@93eb1a58 ask for three flags that flagd-testbed v3.8.0
(``openfeature/test-harness/version.txt``, and the tag pinned in
``docker-compose.yaml`` beside this file) does not seed: ``large-integer-flag``,
``huge-integer-flag`` and ``integral-float-flag``. Until
open-feature/flagd-testbed catches up, both suites fail these scenarios with
``FLAG_NOT_FOUND``, for every resolver alike:

* ``A large integer resolves without loss of precision`` -- untagged;
* ``An integer beyond 32 bits resolves without loss of precision`` -- under
  ``@large-integers``, which both suites declare;
* ``The resolved details name the variant``, the ``large-integer-flag`` row of
  it -- under ``@variants``, which both suites declare. New at spec@26362f85,
  and the same gap rather than a new one: the row asks for the variant
  ``max-int32`` of a flag that is not there, so it fails with the same
  ``FLAG_NOT_FOUND`` as the two above. The other seven rows pass on both
  resolvers, which is the evidence the capability is declared on -- withholding
  it would say flagd does not name variants, which is false, and would
  attribute a missing flag to a capability the provider has.

``integral-float-flag`` is asked for only under ``@numeric-coercion``, which
neither suite declares, so its scenario is skipped rather than failed. The
failures are deliberately left as failures: they say something true about the
stack under test, and an ``xfail`` would say the provider is at fault when it is
the backend that is behind. None of them is a ``KnownDeviation`` either: a
deviation is for a behaviour the *provider* is required to have and does not.

**The seventh failure is the provider's, not the testbed's.** A full run is
``7 failed, 87 passed, 18 skipped`` -- three of the failures above on each
resolver, and one more on in-process alone: ``boolean-flag`` requested as a
Float resolves to ``1.0`` with reason ``STATIC`` and no error code, where the
mandatory wrong-type scenario asks for the caller's default. ``bool`` is a
subclass of ``int`` in Python, so the widening at ``flagd_core.py:113-114`` --
``if isinstance(result.value, int): result.value = float(result.value)`` -- sees
a boolean as an integer, after ``_resolve`` has already let it through for a
Float request. It is the same shape as the boolean-satisfies-an-Integer finding
the suite's own README records against the in-memory provider, and it is a gap
in ``openfeature-flagd-core`` rather than in either resolver's transport: RPC
passes the row, because the server type-checks it. Recorded here rather than
declared as a ``KnownDeviation`` because the scenario is mandatory and
ungated -- it fails visibly on every run, which is the report, and a deviation
would add nothing a reader cannot already see. It is not a testbed gap and does
not go away when the image is bumped.

``targeting-key-flag``, new in the canonical set at the same revision, needs no
testbed change. It is the flag flagd-testbed's own ``targeting.feature`` already
uses -- same key, same ``hit``/``miss`` variants, same uuid -- seeded from
``flags/testing-flags.json`` by the launchpad's ``default`` configuration, so
the three ``@targeting`` scenarios pass on both resolvers as they stand.

The four ``disabled-*`` flags, new in the canonical set at spec@009afe06, need
no testbed change either, and for a sturdier reason than a coincidence of names:
they *are* flagd-testbed's own, from ``flags/disabled-flags.json``, which the
launchpad merges into ``flags/allFlags.json`` along with every other non-
``selector-`` file in ``rawflags`` (``launchpad/pkg/json.go``) and serves under
the ``default`` configuration. So the four ``@disabled-flags`` rows pass on both
resolvers as they stand. The harness also seeds ``disabled-object-flag`` and
``cross-flagset-flag``, which the canonical set deliberately does not ask for --
an Object resolution would need ``@object`` as well, and a scenario needing two
capability tags cannot be one row of a single outline.

The falsy flags used to fail the same way and no longer do. ``ba002ce8`` renamed
them to ``boolean-zero-flag``, ``integer-zero-flag`` and ``string-zero-flag``,
which is what ``flags/zero-flags.json`` in the testbed has always called them,
with the same ``zero``/``non-zero`` variants the scenarios assert. Those three
rows were never a gap in the backend, only a disagreement about names.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import ComposeBackend, RunningBackend
from tests.tck.suite import IN_PROCESS_PORT, RPC_PORT


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, as the TCK's ``tck_backend`` fixture wants it.

    Both resolver ports are declared even though each suite uses one of them,
    because both suites share this stack and the harness checks at startup that
    the Compose file publishes everything it was told about. The launchpad's own
    8080 is exposed automatically and must not be listed.

    The path is absolute rather than relative to the package directory -- which
    is what the harness resolves a relative one against, and where ``poe test``
    runs from -- so that running pytest from the repository root works too.
    """
    return ComposeBackend(
        compose_file=Path(__file__).parent / "docker-compose.yaml",
        backend_ports=[RPC_PORT, IN_PROCESS_PORT],
    )


@pytest.fixture(scope="session")
def closed_port(tck_backend: RunningBackend) -> int:
    """A port on localhost with nothing listening, for the ``@unavailable`` scenarios.

    Discovered by binding and releasing rather than hard-coded, because the
    testbed's own host ports are mapped dynamically and a hard-coded number could
    collide with one. Depending on ``tck_backend`` orders this after the stack has
    taken its ports, which is what makes the remaining race negligible.

    Deliberately not a port on the Compose stack: that has to stay up for the
    whole session, and simulated outages belong to the control API.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
