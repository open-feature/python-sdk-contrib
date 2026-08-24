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
reason, and a scenario carrying a tag this package still calls reserved fails
the run outright rather than being skipped for a capability nobody may claim.
"""

from __future__ import annotations

import typing
from collections.abc import Iterable
from pathlib import Path

import pytest

from openfeature import api

from .capability import Capability, capability_for_marker, expired_reservations
from .compose import ComposeBackend, RunningBackend, run_compose_backend
from .config import TckConfig
from .emitter import ReportEmitter, bind_scenario, observe_provider_name
from .extensions import canonical_tags, is_canonical, uri_for
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
        ReportEmitter(config), "openfeature-tck-report"
    )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Fail the run if any scenario it collected carries a reserved tag.

    A reservation is a name held open for scenarios that do not exist yet, and
    a reserved capability cannot be declared -- :class:`~.config.TckConfig`
    refuses it. So a scenario carrying one reaches the capability gate below
    and is skipped, for a capability nobody is permitted to claim: a question
    put and silently withdrawn. Appendix F calls that the unclaimable
    capability. The run stays green, the report stays well-formed, and nothing
    else here notices, which is why it is checked rather than watched for.

    Two different mistakes end there. The check does not tell them apart,
    because the consequence is identical and the message names both remedies:

    * the specification wrote the scenarios the tag was held open for and
      :data:`~.capability.RESERVED_CAPABILITIES` has not followed --
      ``@targeting`` was reserved until spec revision ``26362f85`` gave it
      three scenarios;
    * an extension of the adopter's own used a reserved name for a tag of its
      own, which is unclaimable from the day the file is written.

    This once fired for the canonical set alone, on the reasoning that only the
    specification can expire a reservation. That much is true and it is beside
    the point: an extension scenario carrying a reserved tag can never run and
    can never be claimed either, which is exactly the failure being surfaced.
    It arrives from the adopter rather than from upstream; the consequence does
    not care. Go and Java check every scenario the run collected, and so does
    this.

    Refused rather than worked around. Treating the tag as declarable here
    would let a run claim a capability against a package that does not know the
    tag exists, and the point of the check is that a human re-reads that set
    against the specification -- or renames their own tag.

    **The two halves have different sources, and only one of them is
    collected.** The canonical tags are read off the packaged files rather than
    off the items, so a ``-k`` or a ``--deselect`` cannot narrow a run past the
    specification's half. An extension's tags have no such source -- the
    directory is found from the adopter's own test module, at the moment
    :func:`~.extensions.feature_paths` is called -- so they come from what was
    collected, as they do in every other language. In practice this hook is
    handed the whole collection before anything is deselected, so a selection
    does not narrow that half either; that is pytest's hook order rather than a
    promise, and the half that must not be narrowable does not lean on it.

    What is read off the collection either way is whether this session runs the
    conformance suite at all. This package is a ``pytest11`` plugin, so the
    hook fires for every pytest run in an environment that merely has it
    installed, and an unrelated test suite has no business failing over the
    contents of these feature files. So the check waits for a canonical
    scenario, which nothing but :func:`~.extensions.feature_paths` produces,
    and it reads tags only from scenarios this suite is running. Go, Java and
    JS have an explicit entry point and no equivalent problem.
    """
    running = False
    carried: set[str] = set()
    for item in items:
        feature = _suite_feature(item)
        if feature is None:
            continue
        running = running or is_canonical(feature)
        carried.update(f"@{marker.name}" for marker in item.iter_markers())

    if not running:
        return

    expired = expired_reservations(carried | canonical_tags())
    if not expired:
        return

    named = " ".join(capability.tag for capability in expired)
    raise pytest.UsageError(
        f"reserved capabilities {named} are carried by scenarios this run "
        f"collected, and a reserved capability cannot be declared -- so every "
        f"scenario carrying one is skipped for a capability nobody is allowed "
        f"to claim, and the report shows a gap the provider may not have. "
        f"Either they came with the canonical feature files, and the scenarios "
        f"they were held open for now exist: remove them from "
        f"RESERVED_CAPABILITIES, so an adoption can declare them and be held "
        f"to them. Or they came from a feature file of your own under "
        f"extensions/, in which case pick tags of your own: a reserved tag "
        f"gates nothing and can never be declared."
    )


def _suite_feature(item: pytest.Item) -> Path | None:
    """The feature file behind a collected node, when this suite is what runs it.

    ``__scenario__`` is what pytest-bdd hangs on the function it generates, and
    it is readable at collection without running a fixture. ``None`` for a node
    that is not a scenario at all, and for a pytest-bdd scenario belonging to
    some other suite that happens to share the session -- neither is this
    suite's to fail.

    Which scenarios are this suite's is decided by
    :func:`~.extensions.uri_for`, the same derivation a report identifies a
    scenario by, so what is checked and what is recorded cannot disagree about
    what the run consisted of.
    """
    scenario = getattr(getattr(item, "function", None), "__scenario__", None)
    filename = getattr(getattr(scenario, "feature", None), "filename", None)
    if not filename:
        return None
    feature = Path(str(filename))
    return feature if uri_for(feature) is not None else None


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
    """Autouse wrapper around :func:`capability_gate`.

    A one-line fixture over a plain function, so the decision it makes can be
    put under test without reaching inside a fixture object for the callable
    pytest wrapped -- which is private, and has moved between pytest versions.

    ``_tck_report_binding`` is requested rather than left to autouse ordering so
    that the scenario has reached its suite before this fixture can skip it. A
    scenario skipped here is exactly the one the conformance report must account
    for, and one that never reached a suite could not be reported at all.
    """
    capability_gate(request)


def capability_gate(request: pytest.FixtureRequest) -> None:
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

    **A capability this SDK cannot express is skipped first, and says so.** Its
    scenarios would be skipped anyway -- nothing may declare it, so nothing
    does -- but with the wrong reason. "The provider does not declare it" reads
    as a decision the provider made, and no provider in this language had one to
    make; a reader of the report has to be able to tell those apart, because only
    the first says anything about the provider. Checked before the declaration
    loop rather than inside it so that a scenario gated by both kinds reports the
    permanent, language-wide reason rather than whichever tag came first off the
    marker iterator. Empty in Python; see
    :data:`~.capability.INEXPRESSIBLE_CAPABILITIES`.
    """
    gated = [
        capability
        for marker in request.node.iter_markers()
        if (capability := capability_for_marker(marker.name)) is not None
    ]
    if not gated:
        return

    inexpressible = inexpressible_skip_reason(gated)
    if inexpressible is not None:
        pytest.skip(inexpressible)

    try:
        config: TckConfig = request.getfixturevalue("tck_config")
    except pytest.FixtureLookupError:
        return

    undeclared = undeclared_skip_reason(gated, config)
    if undeclared is not None:
        pytest.skip(undeclared)


def inexpressible_skip_reason(gated: Iterable[Capability]) -> str | None:
    """Why these scenarios cannot be run in this language at all, or ``None``.

    Says nothing about the provider, and says so, because the alternative
    reading is the one a reader will reach for: a capability missing from a
    report usually means the provider declined. Here nothing declined -- no
    provider in this SDK could be asked -- and Appendix F makes telling those
    two apart the implementation's job rather than the reader's.

    Deterministic when more than one applies: the tags are sorted, so the
    message does not depend on the order markers come off a node.
    """
    for capability in sorted(gated, key=lambda c: c.tag):
        reason = capability.inexpressible_reason
        if reason is not None:
            return (
                f"{capability.tag} cannot be expressed by this SDK, so no provider "
                f"in this language can be asked: {reason}. Nothing about the "
                f"provider under test follows from this skip"
            )
    return None


def undeclared_skip_reason(
    gated: Iterable[Capability], config: TckConfig
) -> str | None:
    """Why this provider is not being asked these scenarios, or ``None``.

    The other half of the pair, and the one that *is* about the provider: it
    declined, and the declaration it did make is quoted so a reader can see what
    was claimed instead.
    """
    for capability in gated:
        if not config.declares(capability):
            return (
                f"provider does not declare capability {capability.tag}. "
                f"Declared: {' '.join(config.sorted_capabilities) or '(none)'}"
            )
    return None


@pytest.fixture(scope="session", autouse=True)
def _tck_release_providers() -> typing.Iterator[None]:
    """Shut down whatever the suite registered once it is over."""
    yield
    api.shutdown()
    api.clear_providers()
