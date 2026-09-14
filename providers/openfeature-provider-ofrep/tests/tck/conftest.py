"""Session fixtures for the OFREP conformance suite, and one recorded deviation.

The container lifecycle belongs to the TCK -- see its README for what
``tck_backend`` does with the declaration below, and Appendix F, "The control
API", for why the stack is started once and never restarted. What is left here is
the declaration, the one wrapper this provider needs around the control, and the
xfail for the single scenario it cannot satisfy.

A full run is ``2 failed, 45 passed, 17 skipped, 1 xfailed``. Both failures ask
for ``large-integer-flag``, which flagd-testbed v3.8.0 does not seed --
open-feature/flagd-testbed#392 adds it, along with the two other canonical flags
the image is missing, and says what each catches. Neither carries a
``KnownDeviation``: the gap is the backend's flag set, not the provider's.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import ComposeBackend, RunningBackend
from tests.tck.settled_control import SettledControl

OFREP_PORT = 8016
"""flagd's OFREP HTTP port, and the one port this provider connects to.

flagd's own default, which the testbed's launchpad does not override. The
launchpad's control port is exposed by the harness and must not be listed here.
"""


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, as the TCK's ``tck_backend`` fixture wants it.

    The Compose file is the same one the flagd adoption uses -- one definition of
    the backend, copied per package -- so it publishes flagd's two resolver ports
    as well. Nothing here declares them, and a port nobody declares is neither
    waited on nor looked up.

    The path is absolute so that pytest run from the repository root works too;
    a relative one resolves against the working directory.
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
    the launchpad's mapped port and awaited ready. The launchpad registers no
    ``/reset``, so every ``prepare_scenario`` takes the harness's documented
    ``/start`` fallback and one 404 is logged per session.

    Wrapped in :class:`SettledControl` because this backend's ``/start`` returns
    before it serves the flag set, and a stateless provider has no initialisation
    to hide that window behind. See that module.
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
