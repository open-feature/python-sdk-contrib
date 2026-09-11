"""One testbed stack and one control, shared by both conformance suites.

The stack is started once per session and **never restarted**. Scenario
isolation comes from the control API instead, because container orchestrators
assign host ports dynamically and cannot reliably preserve them across a
restart: a restarted backend comes back on a different host port, silently
invalidating every provider already pointed at the old one, and the failure
looks like a flaky provider rather than a broken test. See the
no-container-restart invariant in the TCK's ``control-api.yaml``.

``flagd-testbed`` is not modified and the existing e2e suites are untouched: the
TCK drives the testbed's launchpad through the standardised control API, which
the launchpad already implements, and reuses the container lifecycle already in
``tests/e2e``.

**The testbed does not yet serve the whole canonical flag set.** The
conformance assets at spec@fc99d5ac ask for three flags that flagd-testbed
v3.8.0 (``openfeature/test-harness/version.txt``) does not seed:
``large-integer-flag``, ``huge-integer-flag`` and ``integral-float-flag``.
Until open-feature/flagd-testbed catches up, both suites fail these scenarios
with ``FLAG_NOT_FOUND``, for every resolver alike:

* ``A large integer resolves without loss of precision`` -- untagged;
* ``An integer beyond 32 bits resolves without loss of precision`` -- under
  ``@large-integers``, which both suites declare.

``integral-float-flag`` is asked for only under ``@numeric-coercion``, which
neither suite declares, so its scenario is skipped rather than failed. The
failures are deliberately left as failures: they say something true about the
stack under test, and an ``xfail`` would say the provider is at fault when it is
the backend that is behind.

The falsy flags used to fail the same way and no longer do. ``ba002ce8`` renamed
them to ``boolean-zero-flag``, ``integer-zero-flag`` and ``string-zero-flag``,
which is what ``flags/zero-flags.json`` in the testbed has always called them,
with the same ``zero``/``non-zero`` variants the scenarios assert. Those three
rows were never a gap in the backend, only a disagreement about names.
"""

from __future__ import annotations

import socket
import typing

import pytest

from openfeature.contrib.tools.provider_tck import HttpControl
from tests.e2e.flagd_container import FlagdContainer


@pytest.fixture(scope="session")
def flagd_testbed() -> typing.Iterator[FlagdContainer]:
    """The testbed stack, up for the whole session.

    One stack for both suites because one flagd process serves both ports the
    resolvers use -- 8013 for RPC and 8015 for sync -- so there is nothing a
    second stack would isolate.
    """
    container = FlagdContainer()
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest.fixture(scope="session")
def flagd_control(flagd_testbed: FlagdContainer) -> HttpControl:
    """The control API client, shared by both suites.

    Shared rather than one per suite, and that matters: the two suites drive the
    *same* backend, and ``HttpControl`` tracks whether a disconnect has left it
    down so the next scenario starts it rather than merely resetting flag state.
    Two instances would each hold half of that knowledge.

    The launchpad registers only ``/start``, ``/restart``, ``/stop`` and
    ``/change`` (flagd-testbed ``launchpad/main.go``), so ``/reset`` answers 404
    and every ``prepare_scenario`` takes the documented ``/start`` fallback. The
    probe costs one 404 for the whole session.
    """
    return HttpControl(flagd_testbed.get_launchpad_url())


@pytest.fixture(scope="session")
def closed_port(flagd_testbed: FlagdContainer) -> int:
    """A port on localhost with nothing listening, for the ``@unavailable`` scenarios.

    Discovered by binding and releasing rather than hard-coded, because the
    testbed's own host ports are mapped dynamically and a hard-coded number
    could collide with one. Depending on ``flagd_testbed`` orders this after the
    stack has taken its ports, which is what makes the remaining race
    negligible.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])
