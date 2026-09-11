"""The pytest half of the conformance report: turning a run into the two documents.

Kept apart from :mod:`report`, which knows what an envelope *is*, and from
:mod:`messages`, which knows what a Cucumber Messages stream is; neither knows
anything about pytest. Everything here is translation -- a pytest node into a
scenario, a :class:`pytest.TestReport` into a step status, the end of a session
into a pair of files on disk.

Two translations matter.

**Skips.** pytest reports a skip honestly, unlike some runners, and Cucumber's
``SKIPPED`` says the same thing, so a capability-gated scenario reaches the
stream as skipped without anything having to be decided. What the stream does not
say is *why* -- and it does not need to, because the envelope carries the
provider's declaration and the stream carries the scenario's tags, so the reason
for the skip follows from the two. The skip message is carried anyway, on the
setup hook's result, because a person reading the stream should not have to
perform that derivation.

**Expected failures.** A scenario marked ``xfail`` is one pytest reports as
skipped and finishes green on. The provider still did not satisfy it, so the
stream reports it as failed. The acknowledgement belongs in the envelope's
``knownDeviations``, where it is a claim about the provider rather than a
softening of the result.
"""

from __future__ import annotations

import os
import time
import typing
from pathlib import Path

import pytest

from .canonical import (
    PARTIAL_ENV,
    canonical_scenarios,
    describe,
    missing_canonical,
    partial_run_allowed,
)
from .config import TckConfig
from .extensions import (
    collision_problem,
    reserved_prefix_problem,
    uri_collisions,
    uri_for,
)
from .messages import (
    FeatureCatalog,
    ScenarioIdentity,
    ScenarioRun,
    Status,
    StepRun,
    feature_uri,
    worse,
    write_stream,
)
from .report import (
    REPORT_DIR_ENV,
    TCK_DISTRIBUTION,
    TCK_IMPLEMENTATION,
    PhaseOutcome,
    ReportCollector,
    Results,
    SuiteReport,
    control_api_gap,
    distribution_version,
    envelope_file_name,
    normalise_tags,
    stream_file_name,
    write_envelope,
)

__all__ = [
    "COLLECTOR_KEY",
    "ReportEmitter",
    "classify_phase",
    "scenario_identity",
    "scenario_run",
]

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
"""How much of a failure message the stream carries.

A message is for a person reading a comparison page, not for debugging: whoever
ran the suite has the traceback. Whole tracebacks in a published document also
leak local paths.
"""

_SKIPPED = pytest.skip.Exception
"""What ``pytest.skip`` raises, named so a step hook can recognise it."""

_MAX_MISSING = 10
"""How many missing canonical scenarios a failure names before summarising.

Enough to act on and not so many that the reason is lost above them. A run with
one scenario selected is missing twenty-eight, and listing all of them says
nothing the count did not.
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

    filename = str(getattr(feature, "filename", ""))
    path = Path(filename)
    relative = str(getattr(feature, "rel_filename", "") or path.name)

    return ScenarioIdentity(
        # Derived from where the file is, falling back to what pytest-bdd called
        # it. pytest-bdd names a feature by its parent directory joined to its
        # own name, which two files can share: an extension at
        # extensions/gherkin/errors.feature arrives under exactly the uri
        # the canonical errors.feature already occupies, and the payload carries
        # one source per uri.
        uri=uri_for(path) or feature_uri(relative),
        path=path,
        name=str(getattr(scenario, "name", "")),
        example=_example_of(node),
        tags=normalise_tags(tags),
    )


def _examples_tags(node: pytest.Item, scenario: object) -> set[str]:
    """The tags of the Examples block *this row* came from.

    Gherkin allows an Examples block to carry its own tags, so two rows of one
    Scenario Outline can differ in which capability gates them. Those tags are
    not on the scenario, the feature or the rule, so a stream built from those
    three alone would show a row the capability gate skipped as carrying no
    capability at all -- and the envelope's declaration would then not explain
    the skip, which is the one derivation the format asks a consumer to make.

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

    No longer reported -- Cucumber Messages identifies an outline row by the AST
    node id of the table row a pickle was compiled from, which is exact and which
    every runner that emits Messages already carries. This survives as the *join
    key*: it is the one description of a row that both a pytest-bdd node and a
    Gherkin pickle can produce independently, so it is how a node is matched to
    its pickle. Matching on the pickle's name would not work, because the
    compiler interpolates the row's parameters into it and pytest-bdd does not.

    pytest-bdd renders an outline by parametrizing the generated test over one
    dict per row, keyed by the Examples column header, and pytest hangs it on the
    node's callspec. A scenario that is not an outline is not parametrized and
    has no callspec at all, which is why the empty tuple is the answer for one --
    and it matches the empty row of a pickle with a single AST node id.

    Values are passed through as the parser produced them: Gherkin cells are
    strings, and both sides of the join have to agree on ``"1"`` rather than one
    of them guessing it was meant as a number.
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
        self._step_started: dict[str, int] = {}
        config.stash[COLLECTOR_KEY] = self.collector

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        """Enumerate every TCK scenario the session will run.

        At collection rather than as each runs, so that the stream accounts for
        scenarios that never got as far as running a fixture.

        ``trylast`` so that pytest's own deselection -- ``-k``, ``-m``,
        ``--deselect`` -- has already removed what it is going to remove.
        Enumerating before it does would make a filtered run report every
        deselected scenario as collected but never run, which is a true
        statement about a list nobody asked for and drowns the one message that
        matters: which canonical scenarios are missing.
        """
        for item in items:
            identity = scenario_identity(item)
            if identity is not None:
                self.collector.collect(item.nodeid, _group_of(item), identity)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        self.collector.observe(report.nodeid, _phase_outcome(report))

    # -- what each Gherkin step did ------------------------------------------
    #
    # pytest reports a scenario, not its steps. Cucumber Messages records a
    # result per step, and inventing one -- marking all eight steps failed
    # because the scenario failed -- would be saying something untrue about the
    # seven that passed and the ones that were never reached. pytest-bdd's step
    # hooks are the only place the truth is available.

    def pytest_bdd_before_step(
        self, request: pytest.FixtureRequest, step: object
    ) -> None:
        self._step_started[request.node.nodeid] = time.time_ns()

    def pytest_bdd_after_step(self, request: pytest.FixtureRequest) -> None:
        self._finish_step(request, Status.passed)

    def pytest_bdd_step_error(
        self, request: pytest.FixtureRequest, exception: BaseException
    ) -> None:
        # A step that calls ``pytest.skip`` raises through the same hook as one
        # that failed, and the two are not the same result. Told apart by the
        # exception type rather than by the message, which is prose.
        if isinstance(exception, _SKIPPED):
            self._finish_step(request, Status.skipped, exception)
            return
        self._finish_step(request, Status.failed, exception)

    def pytest_bdd_step_func_lookup_error(
        self, request: pytest.FixtureRequest, exception: BaseException
    ) -> None:
        # UNDEFINED rather than FAILED: the step was never run, because nothing
        # claimed to know how to run it. That is a defect in an adoption rather
        # than a finding about the provider, and the stream says which.
        self._step_started.setdefault(request.node.nodeid, time.time_ns())
        self._finish_step(request, Status.undefined, exception)

    def _finish_step(
        self,
        request: pytest.FixtureRequest,
        status: Status,
        exception: BaseException | None = None,
    ) -> None:
        node_id = request.node.nodeid
        finished = time.time_ns()
        self.collector.observe_step(
            node_id,
            StepRun(
                status=status,
                message=_reason(str(exception)) if exception is not None else "",
                exception_type=type(exception).__name__
                if exception is not None
                else "",
                started_ns=self._step_started.pop(node_id, finished),
                finished_ns=finished,
            ),
        )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if session.config.getoption("collectonly", False):
            # Nothing ran, and nothing was meant to. Every check below asks what
            # a run executed, and the answer "nothing" is not a finding here.
            return

        problems = self.collector.resolve(scenario_run)

        # Whether a suite may be published is a property of the run rather than
        # of the report, so it is established whether or not one was asked for.
        # Both checks are made on every suite rather than short-circuited, so a
        # suite with two faults hears about both.
        unpublishable: set[int] = set()
        for suite in self.collector.suites:
            sound = self._identities_are_sound(session, suite)
            complete = self._canonical_set_ran(session, suite)
            if not sound or not complete:
                unpublishable.add(id(suite))

        directory = os.environ.get(REPORT_DIR_ENV, "").strip()
        if not directory:
            return
        for problem in problems:
            self._fail(session, f"tck: {problem}")
        self.write(session, Path(directory), unpublishable)

    def write(
        self,
        session: pytest.Session,
        directory: Path,
        unpublishable: typing.AbstractSet[int] = frozenset(),
    ) -> None:
        """Write every suite's pair of files, failing the session if one cannot be.

        A run that asked for a report and silently did not get one is how a
        publishing pipeline ends up serving a stale result forever, so both a
        write failure and an incomplete document are loud and change the exit
        status rather than being logged and forgotten.
        """
        written: dict[str, str] = {}
        for suite in self.collector.suites:
            if id(suite) in unpublishable:
                continue
            name = suite.config.name
            file_name = envelope_file_name(name)
            if written.get(file_name, name) != name:
                self._fail(
                    session,
                    f"tck: suites {written[file_name]!r} and {name!r} both "
                    f"write {file_name}; give them names that do not collide",
                )
                continue
            written[file_name] = name
            self._write_suite(session, directory, suite)

    def _canonical_set_ran(self, session: pytest.Session, suite: SuiteReport) -> bool:
        """Whether this suite executed every scenario the TCK ships.

        The check a conformance claim rests on that no amount of reading the
        report can supply: the results payload says what happened to the
        scenarios that ran, and says nothing at all about the ones that did not.

        A capability-gated skip counts -- it was asked, and the report accounts
        for it with a reason. An extension scenario does not count and cannot
        close a gap. :data:`~.canonical.PARTIAL_ENV` downgrades the failure to a
        note for someone working on a single scenario; it does not make the run
        publishable, because the report is withheld either way.
        """
        missing = missing_canonical(suite.runs.values())
        if not missing:
            return True

        name = suite.config.name
        total = len(canonical_scenarios())
        headline = (
            f"tck [{name}]: {len(missing)} of {total} canonical scenarios "
            f"did not run, so this run cannot support a conformance claim and no "
            f"report is written for it. The canonical set is fixed by the "
            f"specification; running less of it is not a configuration. Decline "
            f"capabilities your provider does not have through TckConfig instead, "
            f"which reports the scenarios as skipped with their reason"
        )
        if partial_run_allowed():
            self._say(
                session,
                f"{headline}. {PARTIAL_ENV} is set, so the run is not failed for it",
            )
        else:
            self._fail(
                session,
                f"{headline}. To filter anyway while working on one scenario, set "
                f"{PARTIAL_ENV}=1 and accept that the run is not a conformance run",
            )
        for key in missing[:_MAX_MISSING]:
            self._say(session, f"  - {describe(key)}")
        if len(missing) > _MAX_MISSING:
            self._say(session, f"  ... and {len(missing) - _MAX_MISSING} more")
        return False

    def _write_suite(
        self, session: pytest.Session, directory: Path, suite: SuiteReport
    ) -> None:
        name = suite.config.name
        runs = suite.sorted_runs

        catalog = FeatureCatalog()
        try:
            for run in runs:
                catalog.load(run.identity)
        except OSError as error:
            self._fail(
                session,
                f"tck [{name}]: could not read the feature files the run "
                f"executed, so the results payload cannot name them: {error}",
            )
            return

        unmatched = [
            run.identity for run in runs if catalog.pickle_for(run.identity) is None
        ]
        for identity in unmatched:
            # The one failure mode this format exists to rule out: a scenario
            # that ran and is missing from the results. Reported per scenario
            # rather than as a count, because which one it is is the whole point.
            self._fail(
                session,
                f"tck [{name}]: {identity.uri} scenario "
                f"{identity.name!r}{_row(identity)} matched no Gherkin pickle, so "
                f"the results payload does not account for it",
            )

        stream_path = directory / stream_file_name(name)
        try:
            digest = write_stream(
                stream_path,
                catalog,
                runs,
                implementation=TCK_IMPLEMENTATION,
                implementation_version=distribution_version(TCK_DISTRIBUTION),
            )
            envelope = suite.build(Results(location=stream_path.name, digest=digest))
            path = write_envelope(directory, name, envelope)
        except OSError as error:
            self._fail(
                session,
                f"tck [{name}]: could not write the conformance report "
                f"to {directory}: {error}",
            )
            return

        counts = ", ".join(
            f"{count} {status}" for status, count in sorted(suite.counts().items())
        )
        self._say(
            session,
            f"tck [{name}]: report written to {path} with results in "
            f"{stream_path.name} ({counts})",
        )

        gap = control_api_gap(suite.config.control)
        if gap:
            self._say(session, f"tck [{name}]: {gap}")

    def _identities_are_sound(
        self, session: pytest.Session, suite: SuiteReport
    ) -> bool:
        """Whether every feature file this suite ran is named in the payload as itself.

        Two ways it might not be, and both are silent without this. A file that
        is not one of the packaged assets must not be reported under their uri
        prefix, or a consumer reading ``gherkin/errors.feature`` in the stream
        has no way to tell that the specification did not write it. And two
        files must not share a uri, or the stream carries one source for both
        and the second file's scenarios are reported against the first's.

        A suite that fails either writes no report. Refusing is the point: a
        document that presents an adopter's feature file as the specification's
        is worse than no document, because it is the one thing a consumer cannot
        check.
        """
        name = suite.config.name
        runs = suite.sorted_runs

        reserved = [
            problem
            for run in runs
            if (problem := reserved_prefix_problem(run.identity.uri, run.identity.path))
        ]
        for problem in dict.fromkeys(reserved):
            self._fail(session, f"tck [{name}]: {problem}")

        collisions = uri_collisions(
            (run.identity.uri, run.identity.path) for run in runs
        )
        for uri, paths in sorted(collisions.items()):
            self._fail(
                session, f"tck [{name}]: {collision_problem(uri, paths)}"
            )

        return not reserved and not collisions

    def _say(self, session: pytest.Session, message: str) -> None:
        reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if reporter is not None:
            reporter.write_line(message)

    def _fail(self, session: pytest.Session, message: str) -> None:
        self._say(session, message)
        session.exitstatus = pytest.ExitCode.INTERNAL_ERROR


def _row(identity: ScenarioIdentity) -> str:
    if not identity.example:
        return ""
    row = " ".join(f"{header}={cell}" for header, cell in identity.example)
    return f" [{row}]"


def _phase_outcome(report: pytest.TestReport) -> PhaseOutcome:
    """Reduce a pytest phase report to what the conformance report needs."""
    xfail_reason: str | None = getattr(report, "wasxfail", None)
    message = _skip_reason(report) if report.skipped else _failure_reason(report)
    return PhaseOutcome(
        when=report.when or "",
        outcome=report.outcome,
        xfail_reason=xfail_reason,
        message=message,
        start=getattr(report, "start", 0.0),
        stop=getattr(report, "stop", 0.0),
    )


def scenario_run(
    identity: ScenarioIdentity,
    phases: list[PhaseOutcome],
    steps: list[StepRun],
) -> ScenarioRun:
    """Assemble one scenario's execution from what pytest reported about it.

    The scenario's own status is the most serious of its phases', so a scenario
    whose steps passed and whose teardown then blew up is a failed scenario: the
    phase that reports last must not be the one that decides.
    """
    starts = [phase.start for phase in phases if phase.start]
    stops = [phase.stop for phase in phases if phase.stop]
    run = ScenarioRun(
        identity=identity,
        steps=list(steps),
        started_ns=int(min(starts, default=0.0) * 1_000_000_000),
        finished_ns=int(max(stops, default=0.0) * 1_000_000_000),
    )
    for phase in phases:
        status, message = classify_phase(phase)
        result = StepRun(
            status=status,
            message=message,
            started_ns=int(phase.start * 1_000_000_000),
            finished_ns=int(phase.stop * 1_000_000_000),
        )
        if phase.when == "setup":
            run.setup = result
        elif phase.when == "teardown":
            run.teardown = result
        upgraded = worse(run.status, status)
        if upgraded is not run.status:
            # The message belongs to whichever phase decided the verdict, so a
            # teardown failure does not inherit the reason a passing call gave.
            run.message = message
        run.status = upgraded
    return run


def classify_phase(phase: PhaseOutcome) -> tuple[Status, str]:
    """Map one pytest phase onto a Cucumber status.

    The one decision that is not a rename: an expected failure is still a
    failure. pytest reports an ``xfail`` as skipped and exits zero; the provider
    did not satisfy the scenario, and a stream calling it anything else would
    hide exactly the deviation the marker was added to keep visible. The
    acknowledgement goes in the envelope's ``knownDeviations`` instead, which is
    where a claim about the provider belongs.
    """
    if phase.outcome == "skipped" and phase.xfail_reason is not None:
        return Status.failed, _reason(f"expected failure: {phase.xfail_reason}")
    if phase.outcome == "failed":
        return Status.failed, phase.message or "failed"
    if phase.outcome == "skipped":
        return Status.skipped, phase.message or "skipped"
    return Status.passed, ""


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
