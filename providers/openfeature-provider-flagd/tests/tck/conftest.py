"""One testbed stack, declared rather than wired, and shared by both suites.

The container lifecycle belongs to the TCK -- see its README for what
``tck_backend`` does with the declaration below, and Appendix F, "The control
API", for why the stack is started once and never restarted. What is left here
is the declaration and one free port for the scenarios that need a backend that
is not there.

One stack and one ``HttpControl`` serve both suites, because one flagd process
serves both resolver ports: 8013 for RPC and 8015 for sync. The launchpad
registers no ``/reset`` and no ``/healthz``, so every ``prepare_scenario`` takes
the harness's documented ``/start`` fallback and one 404 is logged per session.

**What a full run reports, and what each failure is.** ``8 failed, 119 passed,
3 skipped`` over the two resolvers. Read it here rather than counting: three
distinct causes account for all eight, and only two of them are the provider's.

*Six failures are the backend's flag set.* flagd-testbed v3.8.0 seeds neither
``large-integer-flag`` nor ``integral-float-flag``, so the untagged precision
scenario, the ``max-int32`` row of the ``@variants`` outline and the lossless
``@numeric-coercion`` scenario fail ``FLAG_NOT_FOUND`` on each resolver alike.
open-feature/flagd-testbed#392 seeds all three of the flags the canonical set is
missing and says what each catches; bump the tag in ``docker-compose.yaml``
beside this file when it lands. Left as failures rather than xfailed, because
they are true about the stack under test, and carrying no ``KnownDeviation`` in
either suite: the provider was never given the flag to get wrong.

*One failure is ``openfeature-flagd-core``'s*, on in-process alone:
``boolean-flag`` requested as a Float resolves to ``1.0`` with reason ``STATIC``
and no error code, where the mandatory wrong-type scenario asks for the caller's
default. ``bool`` is a subclass of ``int`` in Python and the int-to-float
widening does not exclude it. Filed as open-feature/python-sdk-contrib#417. RPC
passes the row, because the server type-checks it. No ``KnownDeviation``: the
scenario is mandatory and ungated, so it fails visibly on every run and an entry
would add nothing a reader cannot see.

*One failure is flagd's*, on RPC alone, and it is the one failure here carrying a
``KnownDeviation``: ``float-flag`` (0.5) requested as an Integer comes back as
``0`` with no error code. **The in-process resolver passes that scenario**, which
is why the deviation is recorded against RPC only; ``test_rpc.py`` and
``test_in_process.py`` carry the measurement on each side.

*The three skips are two scenarios.* ``@large-integers`` gates one and is
withheld on both resolvers, so it skips twice; ``@reinitialization`` gates one,
which in-process declares and passes and RPC withholds, so it skips once. Each
suite gives its own reason beside its declaration.

**One finding came out of a scenario that passes**, so neither the results nor
the report has anywhere to put it: the in-process *Shutting down a provider that
cannot reach its backend completes promptly* returns well inside its bound and
leaves a ``PytestUnhandledThreadExceptionWarning`` behind it -- gRPC's
connectivity polling thread raising ``ValueError: Cannot invoke RPC: Channel
closed!`` after ``shutdown`` closed the channel underneath it. Reproducible on
every run, and filed as open-feature/python-sdk-contrib#419. Not a deviation:
nothing required is unmet. It is noted here because a reader who sees the warning
should know it is a recorded finding rather than noise.

The canonical set's ``targeting-key-flag``, four ``disabled-*`` flags and three
falsy flags need no testbed change: they are flagd-testbed's own flags, which is
why the canonical set adopted their names and variants, and the launchpad's
``default`` configuration serves them as they stand.
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
    because both suites share this stack. The Compose file publishes flagd's
    OFREP port as well, which nothing here asks for: it is the same file the
    OFREP adoption uses, and a port nobody declares is neither waited on nor
    looked up.

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
    has taken its ports. Deliberately not a port on the stack, which has to stay
    up -- simulated outages belong to the control API.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
