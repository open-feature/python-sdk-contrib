"""The pytest plugin: capability gating, scenario state, and the shared step vocabulary.

Registered through the ``pytest11`` entry point, so installing this package is
all it takes for the step definitions to be available. pytest-bdd resolves steps
through the fixture system and fixtures from an installed plugin are visible to
every test, which is what keeps an adoption down to one fixture and one call to
:func:`tck_scenarios`.
"""

from __future__ import annotations

import typing

import pytest

from openfeature import api

from .capability import Capability, capability_for_marker
from .config import TckConfig
from .emitter import ReportEmitter, bind_scenario, observe_provider_name
from .state import TckState

# The step modules are registered as plugins in their own right, not merely
# imported. pytest-bdd's decorators inject a generated fixture name into the
# *defining* module's namespace, so a step is only visible to pytest once the
# module defining it is a registered plugin -- importing it here would run the
# decorators but leave those fixtures where pytest never looks.
pytest_plugins = [
    "openfeature.contrib.tools.provider_tck.steps.provider_steps",
    "openfeature.contrib.tools.provider_tck.steps.flag_steps",
    "openfeature.contrib.tools.provider_tck.steps.event_steps",
]


def pytest_configure(config: pytest.Config) -> None:
    """Register the capability tags as markers, and the report emitter.

    pytest-bdd turns every Gherkin tag into a marker with
    ``getattr(pytest.mark, tag)`` without registering it, which raises
    ``PytestUnknownMarkWarning`` for each one -- noise at best, and a hard
    failure in a project configured with ``-W error``.

    The emitter is registered unconditionally even though it writes nothing
    unless :data:`~.report.REPORT_DIR_ENV` is set. Accumulating the outcomes
    costs a dictionary entry per scenario, and deciding at the end of the session
    rather than at the start is one fewer way for a run to discover too late that
    it was not recording.
    """
    for capability in Capability:
        config.addinivalue_line(
            "markers",
            f"{capability.value}: OpenFeature provider TCK capability {capability.tag}",
        )
    config.pluginmanager.register(
        ReportEmitter(config), "openfeature-provider-tck-report"
    )


@pytest.fixture
def tck_state(
    request: pytest.FixtureRequest, tck_config: TckConfig
) -> typing.Iterator[TckState]:
    """Per-scenario state, carried between step definitions."""
    # Resetting here rather than in an autouse fixture ties the reset to the
    # scenarios that actually use the TCK, and guarantees it happens after the
    # capability gate has had its say -- a skipped scenario never touches the
    # backend.
    tck_config.control.prepare_scenario()
    state = TckState(config=tck_config)
    yield state
    # The provider is identified in the report by what it called itself, and the
    # only thing that ever holds an instance is the scenario that made one.
    observe_provider_name(request.config, tck_config, state.provider_name)
    state.teardown()


@pytest.fixture(autouse=True)
def _tck_report_binding(request: pytest.FixtureRequest) -> None:
    """Attribute this scenario to its suite before anything can skip it."""
    bind_scenario(request)


@pytest.fixture(autouse=True)
def _tck_capability_gate(
    request: pytest.FixtureRequest, _tck_report_binding: None
) -> None:
    """Skip a scenario whose capability the provider did not declare.

    ``pytest.skip`` here reports the scenario as skipped **with the reason**,
    which is exactly what the specification asks a TCK implementation to do.
    Nothing about it can be mistaken for a pass.

    The gate keys off the node's markers rather than its requested fixtures.
    pytest-bdd resolves a step's fixtures lazily, as each step runs, so
    ``tck_config`` is not in ``request.fixturenames`` when this autouse fixture
    is set up -- guarding on that silently disabled the gate and let
    ``@unavailable`` scenarios run against a config that never declared it.

    Checking markers first also means the gate costs nothing, and instantiates
    nothing, for tests that are not TCK scenarios.

    ``_tck_report_binding`` is requested rather than left to autouse ordering so
    that the scenario has reached its suite before this fixture can skip it. A
    scenario skipped here is exactly the one the conformance report must account
    for, and one that never reached a suite could not be reported at all.
    """
    gated = [
        capability
        for marker in request.node.iter_markers()
        if (capability := capability_for_marker(marker.name)) is not None
    ]
    if not gated:
        return

    try:
        config: TckConfig = request.getfixturevalue("tck_config")
    except pytest.FixtureLookupError:
        return

    for capability in gated:
        if not config.declares(capability):
            pytest.skip(
                f"provider does not declare capability {capability.tag}. "
                f"Declared: {' '.join(config.sorted_capabilities) or '(none)'}"
            )


@pytest.fixture(scope="session", autouse=True)
def _tck_release_providers() -> typing.Iterator[None]:
    """Shut down whatever the suite registered once it is over."""
    yield
    api.shutdown()
    api.clear_providers()
