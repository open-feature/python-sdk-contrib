"""The pytest plugin: capability gating, scenario state, and the step vocabulary.

Registered through the ``pytest11`` entry point, so installing this package is
all it takes for the step definitions to be available. pytest-bdd resolves steps
through the fixture system and fixtures from an installed plugin are visible to
every test, which is what keeps an adoption down to one fixture and one call to
``scenarios(*feature_paths())``.

The same mechanism is what makes the suite extensible: a step an adopter defines
in their own ``conftest.py`` is resolved by the same fixture lookup as one this
plugin ships, so their scenarios need no glue and no second harness. See
:mod:`~.extensions`.

It is also where the two things a run must refuse to do quietly are checked:
skipping a scenario whose capability was not declared happens loudly, with the
reason, and a reservation the canonical assets have outgrown fails the run
outright rather than skipping scenarios for a capability nobody may claim.
"""

from __future__ import annotations

import typing
from pathlib import Path

import pytest

from openfeature import api

from .capability import Capability, capability_for_marker, expired_reservations
from .compose import ComposeBackend, RunningBackend, run_compose_backend
from .config import TckConfig
from .extensions import canonical_tags, is_canonical
from .state import TckState

# The step modules are registered as plugins in their own right, not merely
# imported. pytest-bdd's decorators inject a generated fixture name into the
# *defining* module's namespace, so a step is only visible to pytest once the
# module defining it is a registered plugin -- importing it here would run the
# decorators but leave those fixtures where pytest never looks.
pytest_plugins = [
    "openfeature.contrib.tools.tck.steps.provider_steps",
    "openfeature.contrib.tools.tck.steps.flag_steps",
    "openfeature.contrib.tools.tck.steps.event_steps",
]


def pytest_configure(config: pytest.Config) -> None:
    """Register the capability tags as markers.

    pytest-bdd turns every Gherkin tag into a marker with
    ``getattr(pytest.mark, tag)`` without registering it, which raises
    ``PytestUnknownMarkWarning`` for each one -- noise at best, and a hard
    failure in a project configured with ``-W error``.
    """
    for capability in Capability:
        config.addinivalue_line(
            "markers",
            f"{capability.value}: OpenFeature provider TCK capability {capability.tag}",
        )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fail the run if a canonical feature carries a tag still called reserved.

    A reservation is a name held open for scenarios that do not exist yet, and
    it is only ever temporary: the specification writes them, the tag starts
    gating something, and the capability becomes declarable. Until this package
    follows, declaring it is refused -- so those scenarios are skipped for a
    capability an adopter cannot claim, and the report shows a gap the provider
    may not have. Appendix F calls that the unclaimable capability, and it has
    no local symptom at all, which is why it is checked rather than watched
    for: ``@targeting`` was reserved until spec revision ``26362f85`` gave it
    three scenarios.

    Refused rather than worked around. Dropping the reservation here instead
    would let a run declare a capability against a package that does not know
    the tag exists, and the point of the check is that a human re-reads
    :data:`~.capability.RESERVED_CAPABILITIES` against the specification.

    Only the canonical set can expire a reservation. An adopter's own feature
    reaching for a reserved tag is a mistake in that file rather than news
    about the specification, so the tags come from the packaged assets and not
    from what was collected -- which also means a narrowed run cannot select
    its way past the check. What *is* read off the collection is whether this
    session runs the conformance suite at all: the plugin is installed for
    every pytest run in the environment, and an unrelated test suite has no
    business failing over the contents of these feature files.
    """
    if not any(_is_canonical_scenario(item) for item in items):
        return

    expired = expired_reservations(canonical_tags())
    if not expired:
        return

    named = " ".join(capability.tag for capability in expired)
    raise pytest.UsageError(
        f"reserved capabilities {named} are carried by the canonical feature "
        f"files, so the scenarios they were held open for now exist. Remove "
        f"them from RESERVED_CAPABILITIES, so an adoption can declare them and "
        f"be held to them -- until then those scenarios are skipped for a "
        f"capability nobody is allowed to claim."
    )


def _is_canonical_scenario(item: pytest.Item) -> bool:
    """Whether a collected node is a scenario from the packaged feature files.

    ``__scenario__`` is what pytest-bdd hangs on the function it generates, and
    it is readable at collection without running a fixture. The feature file is
    then matched by path rather than by the uri it reports, so the check does
    not rest on the derivation in :mod:`~.extensions`.
    """
    scenario = getattr(getattr(item, "function", None), "__scenario__", None)
    filename = getattr(getattr(scenario, "feature", None), "filename", None)
    return bool(filename) and is_canonical(Path(str(filename)))


@pytest.fixture(scope="session")
def tck_backend(compose_backend: ComposeBackend) -> typing.Iterator[RunningBackend]:
    """The Compose stack under test, started once for the whole session.

    Depends on an adopter-supplied ``compose_backend`` fixture returning a
    :class:`~.compose.ComposeBackend`, and yields the started stack's control
    and endpoint. An adoption then reads::

        @pytest.fixture(scope="session")
        def compose_backend() -> ComposeBackend:
            return ComposeBackend(
                compose_file="tests/tck/docker-compose.yaml",
                backend_ports=[8013],
            )

        @pytest.fixture(scope="session")
        def tck_config(tck_backend: RunningBackend) -> TckConfig:
            ...

    Session-scoped rather than module-scoped on purpose: two suites that drive
    the same backend -- flagd's two resolvers, say -- must share one stack *and*
    one control, because the control remembers whether a disconnect left the
    backend down and two instances would each hold half of that knowledge.

    Lazy, like every fixture: a provider with no backend never requests it,
    never defines ``compose_backend``, and never needs Docker or the ``compose``
    extra installed. See :mod:`~.compose`.
    """
    yield from run_compose_backend(compose_backend)


@pytest.fixture
def tck_state(tck_config: TckConfig) -> typing.Iterator[TckState]:
    """Per-scenario state, carried between step definitions."""
    # Resetting here rather than in an autouse fixture ties the reset to the
    # scenarios that actually use the TCK, and guarantees it happens after the
    # capability gate has had its say -- a skipped scenario never touches the
    # backend.
    tck_config.control.prepare_scenario()
    state = TckState(config=tck_config)
    yield state
    state.teardown()


@pytest.fixture(autouse=True)
def _tck_capability_gate(request: pytest.FixtureRequest) -> None:
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
