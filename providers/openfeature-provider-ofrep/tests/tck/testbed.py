"""The flagd testbed, started for the OFREP conformance suite.

flagd serves the **OFREP** HTTP API alongside its own protocols -- port 8016,
next to 8013 for RPC and 8015 for sync -- and ``flagd-testbed``'s compose file
already publishes it. So an OFREP provider needs no backend of its own: it runs
against the same stack, seeded with the same canonical flag set, driven through
the same launchpad control API as the flagd suites. A second stack would be a
second definition of "the canonical flags", which is the one thing a conformance
suite exists to prevent.

**Why this is not ``tests/e2e/flagd_container.FlagdContainer``.** That helper
would be the natural thing to reuse, and it is not importable here: it lives
under ``providers/openfeature-provider-flagd/tests/``, and a package's tests are
not part of its distribution, so nothing in this package can import it. It also
depends on ``grpcio`` and ``grpcio-health-checking`` for its readiness probe,
neither of which the OFREP provider has any other reason to pull in. What is
duplicated is therefore deliberately minimal -- compose up, read two mapped
ports, poll one HTTP endpoint -- and this is a concrete instance of the "no
shared containerised-backend helper" gap the TCK's README already records.

The compose file is reached through the flagd package's ``test-harness``
submodule rather than a second checkout of the same repository. Run
``git submodule update --init`` if it is missing; :func:`testbed_path` says so
rather than failing inside testcontainers.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import typing
import urllib.error
import urllib.request
from pathlib import Path

from testcontainers.compose import DockerCompose

__all__ = ["LAUNCHPAD_PORT", "OFREP_PORT", "FlagdTestbed", "testbed_path"]

OFREP_PORT = 8016
"""flagd's OFREP HTTP port.

flagd's own default (``flags.Int32P("ofrep-port", "r", 8016, ...)`` in flagd's
``cmd/start.go``), published unchanged by the testbed's compose file. The
testbed's launchpad starts flagd with no ``--ofrep-port`` override, so this is
what it listens on.
"""

HEALTH_PORT = 8014
"""flagd's HTTP management port, serving ``/readyz``.

The same endpoint the launchpad itself polls after starting flagd
(``launchpad/pkg/flagd.go``), so waiting on it here means waiting on exactly the
condition the backend considers "up".
"""

LAUNCHPAD_PORT = 8080
"""The testbed's control-API port. ``HttpControl`` is pointed at its mapped host port."""

READY_TIMEOUT_SECONDS = 60.0
READY_POLL_SECONDS = 0.5


def testbed_path() -> Path:
    """Return the directory holding the testbed's compose file.

    Reaching across into the flagd package is a real coupling and is called out
    where it will be read: this package has no submodule of its own, and adding
    a second checkout of ``flagd-testbed`` would let the two drift to different
    testbed versions -- which for a shared canonical flag set is precisely the
    failure the suite is meant to detect rather than to cause.
    """
    providers = Path(__file__).resolve().parents[3]
    path = providers / "openfeature-provider-flagd" / "openfeature" / "test-harness"

    if not (path / "docker-compose.yaml").is_file():
        msg = (
            f"the flagd testbed is not checked out at {path}. It is a git "
            f"submodule of this repository; run 'git submodule update --init' "
            f"from the repository root"
        )
        raise RuntimeError(msg)
    return path


class FlagdTestbed:
    """The testbed stack, and the two host ports the OFREP suite needs from it.

    Started once per session and **never restarted**: compose assigns host ports
    dynamically and cannot preserve them across a restart, so a restart would
    silently invalidate every provider already pointed at the old port. Scenario
    isolation comes from the control API instead -- see the no-container-restart
    invariant in the TCK's ``control-api.yaml``.
    """

    def __init__(self) -> None:
        self._path = testbed_path()
        self._version = (self._path / "version.txt").read_text().rstrip()

        # The compose file substitutes these. FLAGS_DIR is bind-mounted at
        # /flags, where the launchpad writes the flag set it assembles for the
        # configuration it was asked to start, so the directory has to exist
        # before compose runs. A temporary one, because nothing outside the
        # container reads it and a directory inside the checkout would be a
        # test artifact left in the tree.
        self._flags_dir = tempfile.mkdtemp(prefix="ofrep-tck-flags-")
        os.environ["IMAGE"] = "ghcr.io/open-feature/flagd-testbed"
        os.environ["VERSION"] = f"v{self._version}"
        os.environ["FLAGS_DIR"] = self._flags_dir

        self._compose = DockerCompose(
            context=str(self._path),
            compose_file_name="docker-compose.yaml",
            wait=True,
        )

    def start(self) -> FlagdTestbed:
        self._compose.start()
        self._await_ready()
        return self

    def stop(self) -> None:
        """Stop the stack and remove the temporary flag directory.

        The directory comes off in a ``finally`` because a compose failure is
        exactly when it would otherwise be left behind, and it is created in
        ``__init__`` -- so every constructed testbed leaks one until this runs.
        """
        try:
            self._compose.stop()
        finally:
            shutil.rmtree(self._flags_dir, ignore_errors=True)

    def get_ofrep_url(self) -> str:
        """Return the base URL to hand to ``OFREPProvider``.

        The provider appends ``ofrep/v1/evaluate/flags/{key}`` itself
        (``ofrep/__init__.py:115-119``), so this is the bare origin.
        """
        return f"http://localhost:{self._mapped(OFREP_PORT)}"

    def get_launchpad_url(self) -> str:
        return f"http://localhost:{self._mapped(LAUNCHPAD_PORT)}"

    def _mapped(self, port: int) -> int:
        return int(self._compose.get_service_port("flagd", port))

    def _await_ready(self) -> None:
        """Block until flagd answers ``/readyz``.

        ``wait=True`` above waits for compose's own healthcheck, which polls
        ``/healthz`` -- liveness, not readiness. The OFREP endpoint is only
        useful once the flag sources are loaded, so this waits for the stricter
        of the two rather than letting the first scenario race the load.
        """
        url = f"http://localhost:{self._mapped(HEALTH_PORT)}/readyz"
        deadline = time.monotonic() + READY_TIMEOUT_SECONDS
        last: Exception | None = None

        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2.0) as response:  # noqa: S310
                    if response.status == 200:
                        return
            except (urllib.error.URLError, OSError) as err:  # pragma: no cover
                last = err
            time.sleep(READY_POLL_SECONDS)

        msg = f"flagd testbed was not ready within {READY_TIMEOUT_SECONDS}s ({url})"
        raise ConnectionError(msg) from last


def running_testbed() -> typing.Iterator[FlagdTestbed]:
    """Yield a started testbed and stop it afterwards. Used by the session fixture.

    ``start`` is inside the ``try`` on purpose. It brings the stack up and then
    waits for readiness, so a readiness timeout leaves containers running that
    nothing would otherwise stop -- and a suite that cannot reach its backend is
    precisely when a developer is going to run it again.
    """
    testbed = FlagdTestbed()
    try:
        testbed.start()
        yield testbed
    finally:
        testbed.stop()
