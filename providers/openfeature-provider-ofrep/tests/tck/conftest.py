"""Session fixtures for the OFREP conformance suite, and one recorded deviation.

The container lifecycle belongs to the TCK: it starts the Compose file beside
this module once per session, discovers the dynamically mapped host ports, builds
the ``HttpControl`` against the launchpad and waits for it to accept commands.
What is left here is the declaration, the one wrapper this provider needs around
the control, and the xfail for the single scenario it cannot satisfy.

The stack is started once and never restarted, because Compose assigns host
ports dynamically and cannot preserve them across a restart: a restarted backend
comes back on a different port, silently invalidating a provider already pointed
at the old one, and the failure reads as a flaky provider rather than a broken
test. Scenario isolation comes from the control API instead -- see the
no-container-restart invariant in the TCK's ``control-api.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import ComposeBackend, RunningBackend
from tests.tck.settled_control import SettledControl

OFREP_PORT = 8016
"""flagd's OFREP HTTP port.

flagd's own default (``flags.Int32P("ofrep-port", "r", 8016, ...)`` in flagd's
``cmd/start.go``). The testbed's launchpad starts flagd with no
``--ofrep-port`` override, so this is what it listens on, and it is the one port
the provider connects to. The launchpad's own 8080 is exposed automatically.
"""


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, as the TCK's ``tck_backend`` fixture wants it.

    The path is absolute rather than relative to the package directory -- which
    is what the harness resolves a relative one against, and where ``poe test``
    runs from -- so that running pytest from the repository root works too.
    """
    return ComposeBackend(
        compose_file=Path(__file__).parent / "docker-compose.yaml",
        backend_ports=[OFREP_PORT],
    )


@pytest.fixture(scope="session")
def ofrep_base_url(tck_backend: RunningBackend) -> str:
    """The origin flagd serves OFREP on, resolved once the stack is up.

    A fixture rather than a constant the suite module reads, because the mapped
    host port does not exist until the stack has started. The provider appends
    ``ofrep/v1/evaluate/flags/{key}`` itself (``ofrep/__init__.py:115-119``), so
    this is the bare origin.
    """
    endpoint = tck_backend.endpoint
    return f"http://{endpoint.host}:{endpoint.port(OFREP_PORT)}"


@pytest.fixture(scope="session")
def ofrep_control(tck_backend: RunningBackend, ofrep_base_url: str) -> SettledControl:
    """The control API client, wrapped in a wait for the flag set to be served.

    ``tck_backend.control`` is the TCK's own ``HttpControl``, already pointed at
    the launchpad's mapped port and awaited ready. The launchpad registers only
    ``/start``, ``/restart``, ``/stop`` and ``/change`` (flagd-testbed
    ``launchpad/main.go:29-32``), so ``/reset`` answers 404 and every
    ``prepare_scenario`` takes the documented ``/start`` fallback. The probe
    costs one 404 for the whole session.

    Wrapped in :class:`SettledControl` because this backend's ``/start``
    returns before it serves the flag set -- which ``control-api.yaml`` forbids
    in those words -- and a stateless provider has no initialisation to hide
    that window behind. See that module: it is a named workaround for one
    backend's defect, which is where Appendix F says such a wait belongs, and it
    is a readiness probe over the provider's own public endpoint rather than a
    sleep.
    """
    return SettledControl(tck_backend.control, ofrep_base_url)


# ---------------------------------------------------------------------------
# One known deviation, recorded rather than hidden.
#
# A conformance suite that quietly goes green on a scenario it ran and failed is
# as bad as one that goes green on a scenario it skipped. So the single scenario
# this provider cannot satisfy is marked xfail(strict=True), which keeps it in
# the report with its reason attached and fails the suite the moment it starts
# passing -- so the marker is removed when the bug is fixed rather than
# lingering as a lie. Same mechanism, and same bug, as the TCK's own self-test
# (tools/openfeature-tck/tests/conftest.py).

_BOOL_AS_INT = (
    "test_requesting_the_wrong_type_returns_the_code_default[boolean-flag-Integer-1]"
)

_REASON = (
    "bool satisfies an Integer request. OFREP is an untyped protocol -- the "
    "backend returns the JSON value with no knowledge of the requested type -- so "
    "the whole type check is the provider's, at ofrep/__init__.py:244-256: "
    "FlagType.INTEGER maps to `int` and the check is isinstance(value, int), which "
    "bool is a subclass of in Python. boolean-flag requested as an Integer "
    "therefore returns True with reason STATIC and no error code, where the "
    "specification requires the code default and TYPE_MISMATCH. The Python SDK "
    "client type-checks the same way, so fixing only one of the two is not enough. "
    "See https://github.com/open-feature/python-sdk/issues/619"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.name == _BOOL_AS_INT:
            item.add_marker(pytest.mark.xfail(reason=_REASON, strict=True))
