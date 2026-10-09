"""Session fixtures for the OFREP conformance suite, and one recorded deviation.

A full run is ``2 failed, 45 passed, 17 skipped, 1 xfailed``. Both failures ask
for ``large-integer-flag``, which no released flagd-testbed seeds --
open-feature/flagd-testbed#392 adds it, along with the two other canonical flags
the image is missing. Neither carries a ``KnownDeviation``: the gap is the
backend's flag set, not the provider's.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import BackendControl, ComposeBackend, RunningBackend

OFREP_PORT = 8016
"""flagd's OFREP HTTP port, and the one port this provider connects to.

The launchpad's control port is exposed by the harness and must not be listed
here.
"""


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, for the TCK's ``tck_backend`` fixture.

    The Compose file is the same one the flagd adoption uses -- one definition
    of the backend, copied per package -- so it also publishes flagd's two
    resolver ports, which nothing here declares.

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
def ofrep_control(tck_backend: RunningBackend) -> BackendControl:
    """The control API client, used exactly as the harness provides it.

    Deliberately unwrapped, and do not add a wait here. This backend's
    ``/start`` can return before the reseeded flags are actually served, so it
    is tempting to poll the OFREP endpoint until they are -- but that made this
    suite's results incomparable with every other adoption run against the same
    backend: this one read a clean floor while the others bounced, and the
    difference was the wait rather than the provider. The defect is
    open-feature/flagd-testbed#394 and belongs there.

    So repeat a red run before blaming the provider: the race moves between
    scenarios, a real defect does not.
    """
    return tck_backend.control


# The single scenario this provider cannot satisfy, marked xfail(strict=True) so
# that it stays in the report with its reason attached and the suite fails the
# moment it starts passing -- the marker goes when the bug is fixed rather than
# lingering as a lie.

_BOOL_AS_INT = (
    "test_requesting_the_wrong_type_returns_the_code_default[boolean-flag-Integer-1]"
)

_REASON = (
    "bool satisfies an Integer request. OFREP carries no requested type on the "
    "wire, so the whole type check is the provider's, at "
    "ofrep/__init__.py:244-256: FlagType.INTEGER maps to `int` and the check is "
    "isinstance(value, int), which bool is a subclass of in Python. boolean-flag "
    "requested as an Integer therefore returns True with reason STATIC and no "
    "error code, where the specification requires the code default and "
    "TYPE_MISMATCH. The Python SDK client type-checks the same way, so fixing "
    "only one of the two is not enough. "
    "See https://github.com/open-feature/python-sdk/issues/619"
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.name == _BOOL_AS_INT:
            item.add_marker(pytest.mark.xfail(reason=_REASON, strict=True))
