"""One testbed stack, declared rather than wired, and shared by both suites.

One flagd process serves both resolver ports -- 8013 for RPC, 8015 for sync --
so one stack and one ``HttpControl`` serve both suites.

**A full run is ``8 failed, 119 passed, 3 skipped``.** All eight failures have
one of three causes, and only two of them are the provider's:

* Six are the backend's flag set. No released flagd-testbed seeds
  ``large-integer-flag`` or ``integral-float-flag``, so three scenarios fail
  ``FLAG_NOT_FOUND`` on each resolver alike. open-feature/flagd-testbed#392
  seeds them; bump the tag in ``docker-compose.yaml`` beside this file when it
  lands. Carrying no ``KnownDeviation``: the provider was never given the flag.
* One is ``openfeature-flagd-core``'s, on in-process alone. ``boolean-flag``
  requested as a Float resolves to ``1.0`` rather than the caller's default,
  because ``bool`` is a subclass of ``int``: python-sdk-contrib#417. RPC passes
  the row, because the server type-checks it.
* One is flagd's, on RPC alone, and is the only failure here carrying a
  ``KnownDeviation``: ``float-flag`` (0.5) as an Integer comes back as ``0``.
  In-process passes that scenario, hence the deviation on RPC only.

The three skips are two scenarios: ``@large-integers``, withheld on both
resolvers, and ``@reinitialization``, withheld on RPC alone.

One finding has nowhere else to go, because its scenario *passes*: in-process
shutdown-under-outage leaves a ``PytestUnhandledThreadExceptionWarning`` from
gRPC's connectivity thread behind it on every run, python-sdk-contrib#419. Noted
so a reader knows the warning is recorded rather than noise.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import ComposeBackend, RunningBackend
from tests.tck.suite import IN_PROCESS_PORT, RPC_PORT


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, for the TCK's ``tck_backend`` fixture.

    Both resolver ports are declared even though each suite uses one of them,
    because both suites share this stack.

    The path is absolute so that pytest run from the repository root works too;
    a relative one resolves against the working directory.
    """
    return ComposeBackend(
        compose_file=Path(__file__).parent / "docker-compose.yaml",
        backend_ports=[RPC_PORT, IN_PROCESS_PORT],
    )


@pytest.fixture(scope="session")
def closed_port(tck_backend: RunningBackend) -> int:
    """A port on localhost with nothing listening, for the ``@unavailable`` scenarios.

    Discovered by binding and releasing rather than hard-coded, because the
    stack's own host ports are mapped dynamically and a fixed number could
    collide with one; depending on ``tck_backend`` orders this after the stack
    has taken its ports.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
