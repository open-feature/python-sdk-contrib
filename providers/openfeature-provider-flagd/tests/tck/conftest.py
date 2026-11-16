"""One testbed stack, declared rather than wired, and shared by both suites.

One flagd process serves both resolver ports -- 8013 for RPC, 8015 for sync --
so one stack and one ``HttpControl`` serve both suites.

**A full run is ``5 failed, 648 passed, 75 skipped``**, 364 scenarios per
resolver: the canonical set plus flagd-testbed's ``tck-extensions``. In-process
fails 3, RPC 2, for two causes:

* ``boolean-flag`` requested as a Float resolves to ``1.0`` on in-process alone,
  because ``bool`` is a subclass of ``int``: python-sdk-contrib#417.
* The two custom-certificate scenarios, on both resolvers. The TCK resolves the
  stack's host as ``0.0.0.0``, a bind address the server certificate does not
  name, so TLS verification fails; ``localhost`` passes both.

The skips are the extension scenarios selected for the other resolver, the
``@targetURI`` and ``@fractional-v2`` exclusions in ``suite.py``,
``@large-integers`` on both resolvers and ``@reinitialization`` on RPC.

One finding has nowhere else to go, because its scenario *passes*: in-process
shutdown-under-outage leaves a ``PytestUnhandledThreadExceptionWarning`` from
gRPC's connectivity thread behind it on every run, python-sdk-contrib#419. Noted
so a reader knows the warning is recorded rather than noise.
"""

from __future__ import annotations

import re
import shutil
import socket
import typing
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import ComposeBackend, RunningBackend
from tests.tck.steps import *  # noqa: F403
from tests.tck.suite import (
    ENVOY_FORBIDDEN_PORT,
    ENVOY_SERVICE,
    IN_PROCESS_PORT,
    RPC_PORT,
    TESTBED,
)

EXTENSIONS = TESTBED / "tck-extensions"


def pytest_configure(config: pytest.Config) -> None:
    """Copy flagd-testbed's TCK extensions to ``extensions/`` beside the suites.

    The TCK runs extension scenarios from a directory of that name beside the
    test module, and identifies them by the path below it. Their tags are
    registered as markers, as the TCK registers its own.
    """
    if not EXTENSIONS.is_dir():
        msg = f"{EXTENSIONS} is missing: run `git submodule update --init`"
        raise pytest.UsageError(msg)
    target = Path(__file__).parent / "extensions"
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir()
    tags: set[str] = set()
    for feature in EXTENSIONS.glob("*.feature"):
        shutil.copy(feature, target)
        for line in feature.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("@"):
                tags.update(re.findall(r"@([\w-]+)", line))
    for tag in sorted(tags):
        config.addinivalue_line("markers", f"{tag}: flagd-testbed extension tag")


@pytest.fixture(scope="session")
def compose_backend() -> ComposeBackend:
    """The stack under test, for the TCK's ``tck_backend`` fixture.

    flagd-testbed's own Compose file, so the image follows the submodule pin,
    with the envoy sidecar the ``@forbidden`` scenario connects through. Both
    resolver ports are declared because both suites share this stack.
    """
    return ComposeBackend(
        compose_file=TESTBED / "docker-compose.yaml",
        backend_service="flagd",
        backend_ports=[RPC_PORT, IN_PROCESS_PORT],
        additional_ports={ENVOY_SERVICE: [ENVOY_FORBIDDEN_PORT]},
    )


@pytest.fixture(scope="session")
def provider_options() -> dict[str, typing.Any]:
    """Provider options the current extension scenario set; see ``suite.build_config``."""
    return {}


@pytest.fixture(autouse=True)
def _clear_provider_options(
    provider_options: dict[str, typing.Any],
) -> typing.Iterator[None]:
    yield
    provider_options.clear()


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
