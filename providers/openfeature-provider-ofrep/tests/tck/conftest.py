"""Session fixtures for the OFREP conformance suite, and one recorded deviation.

The stack is started once and never restarted, because compose assigns host
ports dynamically and cannot preserve them across a restart: a restarted backend
comes back on a different port, silently invalidating a provider already pointed
at the old one, and the failure reads as a flaky provider rather than a broken
test. Scenario isolation comes from the control API instead -- see the
no-container-restart invariant in the TCK's ``control-api.yaml``.
"""

from __future__ import annotations

import typing

import pytest

from openfeature.contrib.tools.provider_tck import HttpControl
from tests.tck.settled_control import SettledControl
from tests.tck.testbed import FlagdTestbed, running_testbed


@pytest.fixture(scope="session")
def flagd_testbed() -> typing.Iterator[FlagdTestbed]:
    """The testbed stack, up for the whole session."""
    yield from running_testbed()


@pytest.fixture(scope="session")
def ofrep_control(flagd_testbed: FlagdTestbed) -> SettledControl:
    """The control API client, pointed at the testbed's launchpad.

    The launchpad registers only ``/start``, ``/restart``, ``/stop`` and
    ``/change`` (flagd-testbed ``launchpad/main.go:29-32``), so ``/reset``
    answers 404 and every ``prepare_scenario`` takes the documented ``/start``
    fallback. The probe costs one 404 for the whole session.

    Wrapped in :class:`SettledControl` because ``/start`` returns before the
    backend serves the flag set, and a stateless provider has no initialisation
    to hide that window behind. See that module -- it is a finding about the
    control API's guarantee, not a convenience.
    """
    return SettledControl(
        HttpControl(flagd_testbed.get_launchpad_url()),
        flagd_testbed.get_ofrep_url(),
    )


# ---------------------------------------------------------------------------
# One known deviation, recorded rather than hidden.
#
# A conformance suite that quietly goes green on a scenario it ran and failed is
# as bad as one that goes green on a scenario it skipped. So the single scenario
# this provider cannot satisfy is marked xfail(strict=True), which keeps it in
# the report with its reason attached and fails the suite the moment it starts
# passing -- so the marker is removed when the bug is fixed rather than
# lingering as a lie. Same mechanism, and same bug, as the TCK's own self-test
# (tools/openfeature-provider-tck/tests/conftest.py).

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
