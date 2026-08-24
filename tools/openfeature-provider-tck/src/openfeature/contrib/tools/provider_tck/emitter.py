"""The pytest half of the conformance report: turning a run into the document.

Kept apart from :mod:`report`, which knows what a report *is* and nothing about
pytest. Everything here is translation -- a pytest node into a scenario, a
:class:`pytest.TestReport` into an :class:`~.report.Outcome`, the end of a
session into a file on disk.

The translation that matters is the one for skips. pytest reports a skip
honestly, unlike some runners, but "skipped" alone does not distinguish a
capability the provider never declared from a scenario the run had some other
reason not to execute, and the report format does. So the decision is made
against the scenario's own tags and the suite's declared capabilities rather than
against the wording of a skip message.
"""

from __future__ import annotations

import os
import typing
from pathlib import Path

import pytest

from .config import TckConfig
from .report import (
    REPORT_DIR_ENV,
    Outcome,
    PhaseOutcome,
    ReportCollector,
    ScenarioIdentity,
    normalise_tags,
    report_file_name,
    write_report,
)

__all__ = ["COLLECTOR_KEY", "ReportEmitter", "classify_phase", "scenario_identity"]

COLLECTOR_KEY = pytest.StashKey[ReportCollector]()
"""Where the session's collector lives, so a fixture can reach it from a request."""

_EXAMPLE_PARAM = "_pytest_bdd_example"
"""The parameter pytest-bdd renders a Scenario Outline over.

An implementation detail of pytest-bdd, named here rather than spelled inline so
that a version bump that renames it fails in one place. The alternative -- asking
the scenario template for its examples -- would have to work out which row *this*
node is, which is the question the callspec already answers.
"""

_MAX_REASON = 500
"""How much of a failure message the report carries.

A reason is for a person reading a comparison page, not for debugging: whoever
ran the suite has the traceback. Whole tracebacks in a published document also
leak local paths.
"""


def scenario_identity(node: pytest.Item) -> ScenarioIdentity | None:
    """Describe a pytest node as a Gherkin scenario, or return ``None``.

    ``__scenario__`` is what pytest-bdd hangs on the function it generates, so
    its presence is also the test for "is this a TCK scenario at all" -- and it
    is readable at collection, without running a single fixture, which is what
    lets a scenario skipped before its first step still be accounted for.
    """
    scenario = getattr(getattr(node, "function", None), "__scenario__", None)
    if scenario is None:
        return None

    feature = getattr(scenario, "feature", None)
    tags: set[str] = set(getattr(scenario, "tags", None) or ())
    tags |= set(getattr(feature, "tags", None) or ())
    rule = getattr(scenario, "rule", None)
    if rule is not None:
        tags |= set(getattr(rule, "tags", None) or ())
    tags |= _examples_tags(node, scenario)

    return ScenarioIdentity(
        feature=Path(str(getattr(feature, "filename", ""))).stem,
        name=str(getattr(scenario, "name", "")),
        example=_example_of(node),
        tags=normalise_tags(tags),
    )


def _examples_tags(node: pytest.Item, scenario: object) -> set[str]:
    """The tags of the Examples block *this row* came from.

    Gherkin allows an Examples block to carry its own tags, so two rows of one
    Scenario Outline can differ in which capability gates them. Those tags are not
    on the scenario, the feature or the rule, so a report built from those three
    alone would show a row the capability gate skipped as carrying no capability
    at all -- and it would then be classified ``not-applicable`` rather than
    ``not-declared``, which is precisely the distinction Appendix F asks a report
    to keep. It would also not count towards the capability rollup.

    Resolved by intersecting the tags the scenario's Examples blocks declare with
    the markers pytest actually put on this node: pytest-bdd attaches an Examples
    block's tags as marks on that block's parameter sets, so the intersection
    names this row's blocks without having to work out which block a row came
    from, and admits nothing that is not a Gherkin tag of this scenario.

    No canonical feature file uses per-Examples tags today, so this is latent --
    but it is latent in the direction of under-reporting a skip, which is the one
    failure mode the format exists to rule out.
    """
    declared: set[str] = set()
    for examples in getattr(scenario, "examples", None) or ():
        declared |= set(getattr(examples, "tags", None) or ())
    if not declared:
        return set()
    return declared & {marker.name for marker in node.iter_markers()}


def _example_of(node: pytest.Item) -> tuple[tuple[str, str], ...]:
    """The Examples row this node came from, keyed by column header.

    Every row of a Scenario Outline shares one scenario name, so the row is what
    tells eleven otherwise identical entries apart -- and in this suite one row
    of the type-mismatch matrix genuinely differs in outcome from its ten
    siblings. The row goes in its own field rather than into a mangled name
    because the parameters *are* the identity and they come from the feature
    file, whereas a name format would be a rule about this runner: pytest-bdd's
    own id for the row above is ``boolean-flag-Integer-1``, which no other
    language's runner has any reason to reproduce.

    pytest-bdd renders an outline by parametrizing the generated test over one
    dict per row, keyed by the Examples column header, and pytest hangs it on the
    node's callspec. A scenario that is not an outline is not parametrized and
    has no callspec at all, which is why the empty tuple -- and therefore an
    omitted field -- is the answer for one.

    Values are passed through as the parser produced them: Gherkin cells are
    strings, and the report says what the table said rather than guessing that
    ``1`` was meant as a number.
    """
    params = getattr(getattr(node, "callspec", None), "params", None)
    if not isinstance(params, dict):
        return ()
    row = params.get(_EXAMPLE_PARAM)
    if not isinstance(row, dict):
        return ()
    # Column order, as the feature file wrote it, because dicts preserve
    # insertion order and pytest-bdd builds this one from the header row.
    return tuple((str(header), str(cell)) for header, cell in row.items())


def _group_of(node: pytest.Item) -> str:
    """Which module a scenario was generated into.

    pytest-bdd's ``scenarios()`` injects its tests into the module that called
    it, and a module resolves one ``tck_config``, so the module is what says
    which suite a scenario belongs to. Two modules sharing a ``tck_config`` from
    a conftest are two groups pointing at one suite, which is exactly right.
    """
    return node.nodeid.partition("::")[0]


class ReportEmitter:
    """Collects outcomes for the session and writes one report per suite.

    A plugin object rather than module-level hook functions because
    ``pytest_runtest_logreport`` is handed a report and nothing else: the state
    it has to reach has to come from somewhere, and an instance is a less
    surprising somewhere than a module global.
    """

    def __init__(self, config: pytest.Config) -> None:
        self.collector = ReportCollector()
        config.stash[COLLECTOR_KEY] = self.collector

    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Enumerate every TCK scenario the session collected.

        At collection rather than as each runs, so that the document accounts for
        scenarios that never got as far as running a fixture.
        """
        for item in items:
            identity = scenario_identity(item)
            if identity is not None:
                self.collector.collect(item.nodeid, _group_of(item), identity)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.collector.observe(report.nodeid, _phase_outcome(report))

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        directory = os.environ.get(REPORT_DIR_ENV, "").strip()
        if not directory:
            return
        self.write(session, Path(directory))

    def write(self, session: pytest.Session, directory: Path) -> None:
        """Write every suite's report, failing the session if one cannot be written.

        A run that asked for a report and silently did not get one is how a
        publishing pipeline ends up serving a stale result forever, so both a
        write failure and an incomplete document are loud and change the exit
        status rather than being logged and forgotten.
        """
        for problem in self.collector.resolve(classify_phase):
            self._fail(session, f"provider-tck: {problem}")

        written: dict[str, str] = {}
        for suite in self.collector.suites:
            name = suite.config.name
            file_name = report_file_name(name)
            if written.get(file_name, name) != name:
                self._fail(
                    session,
                    f"provider-tck: suites {written[file_name]!r} and {name!r} both "
                    f"write {file_name}; give them names that do not collide",
                )
                continue
            written[file_name] = name

            try:
                path = write_report(directory, name, suite.build())
            except OSError as error:
                self._fail(
                    session,
                    f"provider-tck [{name}]: could not write the conformance report "
                    f"to {directory}: {error}",
                )
                continue
            counts = ", ".join(
                f"{count} {outcome}"
                for outcome, count in sorted(suite.counts().items())
            )
            self._say(
                session, f"provider-tck [{name}]: report written to {path} ({counts})"
            )

    def _say(self, session: pytest.Session, message: str) -> None:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(message)

    def _fail(self, session: pytest.Session, message: str) -> None:
        self._say(session, message)
        session.exitstatus = pytest.ExitCode.INTERNAL_ERROR


def _phase_outcome(report: pytest.TestReport) -> PhaseOutcome:
    """Reduce a pytest phase report to what the conformance report needs."""
    xfail_reason: str | None = getattr(report, "wasxfail", None)
    message = _skip_reason(report) if report.skipped else _failure_reason(report)
    return PhaseOutcome(
        when=report.when or "",
        outcome=report.outcome,
        xfail_reason=xfail_reason,
        message=message,
        duration=report.duration,
    )


def classify_phase(
    phase: PhaseOutcome, identity: ScenarioIdentity, config: TckConfig
) -> tuple[Outcome, str] | None:
    """Map one phase onto an outcome, or onto nothing.

    Nothing is the answer for a setup or teardown that simply worked: it says
    nothing about the scenario, and letting it speak would overwrite what the
    call phase already established.
    """
    if phase.outcome == "skipped" and phase.xfail_reason is not None:
        # An expected failure is still a failure. The provider did not satisfy
        # the scenario, and a report calling it anything else would hide exactly
        # the deviation the marker was added to keep visible.
        return Outcome.FAILED, _reason(f"expected failure: {phase.xfail_reason}")
    if phase.outcome == "failed":
        return Outcome.FAILED, phase.message or "failed"
    if phase.outcome == "skipped":
        return _skipped(phase, identity, config)
    if phase.when == "call":
        return Outcome.PASSED, ""
    return None


def _skipped(
    phase: PhaseOutcome, identity: ScenarioIdentity, config: TckConfig
) -> tuple[Outcome, str]:
    """Tell a capability skip apart from every other kind.

    Decided from the scenario's tags and the suite's declared capabilities rather
    than from the skip message, because the message is prose and the distinction
    is not. Anything else that skipped a scenario -- a marker an adopter applied,
    a step calling ``pytest.skip`` -- is reported as not applicable: it did not
    run, and not because a capability was left undeclared.
    """
    undeclared = [
        capability.tag
        for capability in identity.capabilities()
        if not config.declares(capability)
    ]
    if undeclared:
        return Outcome.NOT_DECLARED, phase.message or (
            f"provider does not declare {' '.join(undeclared)}"
        )
    return Outcome.NOT_APPLICABLE, phase.message or "skipped"


def _skip_reason(report: pytest.TestReport) -> str:
    longrepr = report.longrepr
    if isinstance(longrepr, tuple) and len(longrepr) == 3:
        return _reason(str(longrepr[2]).removeprefix("Skipped: "))
    return _reason(str(longrepr)) if longrepr else ""


def _failure_reason(report: pytest.TestReport) -> str:
    message = getattr(getattr(report.longrepr, "reprcrash", None), "message", "")
    if not message:
        message = str(report.longrepr) if report.longrepr else ""
    return _reason(message)


def _reason(message: str) -> str:
    collapsed = " ".join(message.split())
    if len(collapsed) <= _MAX_REASON:
        return collapsed
    return collapsed[: _MAX_REASON - 1].rstrip() + "…"


def observe_provider_name(
    config: pytest.Config, tck_config: TckConfig, provider_name: str | None
) -> None:
    """Record what the provider called itself, for the suite the run is in.

    The provider's own metadata name rather than the suite name, because the two
    answer different questions: the suite name is chosen to read well in a
    failure message, which makes it the configuration and it is reported as one.
    """
    collector: ReportCollector | None = config.stash.get(COLLECTOR_KEY, None)
    if collector is not None and provider_name:
        collector.suite_for(tck_config).observe_provider_name(provider_name)


def bind_scenario(request: pytest.FixtureRequest) -> None:
    """Tell the collector which suite this scenario's module is testing.

    Called from an autouse fixture that the capability gate depends on, so that a
    scenario the gate stops has still contributed its suite. Only one scenario of
    a module has to get this far, but the gate skips whole capabilities at a
    time, and a module all of whose scenarios were skipped would otherwise have
    no report to be written to.
    """
    collector: ReportCollector | None = request.config.stash.get(COLLECTOR_KEY, None)
    if collector is None or scenario_identity(request.node) is None:
        # Checked before asking for the config so that a test which is not a TCK
        # scenario instantiates nothing, which is the same bargain the capability
        # gate makes.
        return
    try:
        tck_config = typing.cast(TckConfig, request.getfixturevalue("tck_config"))
    except pytest.FixtureLookupError:
        return
    collector.bind(request.node.nodeid, tck_config)
