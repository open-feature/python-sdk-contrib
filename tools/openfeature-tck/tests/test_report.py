"""What the conformance report must never do.

The report exists because a runner's summary cannot be checked by anything
downstream. So the tests that matter here are not about JSON shape; they are
about the two properties a consumer is entitled to assume, neither of which is
guaranteed by the code that happens to assemble the documents:

* a scenario skipped for an undeclared capability is never reported as passed,
  and the reason it was skipped is recoverable;
* every scenario the run collected appears exactly once, which is what makes the
  first property checkable rather than merely asserted -- a document that quietly
  dropped what it skipped would satisfy the letter of it and still mislead.

Both are now checked against the *results payload* rather than against the
envelope, because that is where the results moved: a run writes an envelope and a
`Cucumber Messages`_ stream beside it, and the envelope says only what was tested,
what the provider claims and where the results are. The assertions are written
the way a consumer reads the stream -- a test case is as bad as its worst step --
so that what these tests check is what a consumer would see rather than an
internal representation.

Both are checked against a real pytest session in a subprocess, because both are
properties of how the suite runs rather than of how the documents are assembled.
That session is also the only place a skip, a pass and a failure occur together,
and the only place the payload can be seen to disagree with the runner's summary
-- which it does, deliberately, for a known deviation.

.. _Cucumber Messages: https://github.com/cucumber/messages
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import (
    DECLARABLE_CAPABILITIES,
    RESERVED_CAPABILITIES,
    Capability,
    KnownDeviation,
    TckConfig,
    features_path,
)
from openfeature.contrib.tools.tck.emitter import (
    classify_phase,
    scenario_run,
)
from openfeature.contrib.tools.tck.messages import (
    MESSAGES_FORMAT,
    ScenarioIdentity,
    Status,
    StepRun,
    _Pickle,
    _step_runs,
    feature_uri,
)
from openfeature.contrib.tools.tck.report import (
    REPORT_DIR_ENV,
    PhaseOutcome,
    Results,
    SuiteReport,
    control_api_of,
    envelope_file_name,
    normalise_tags,
    spec_revision,
    stream_file_name,
)

# The generated suite's name is deliberately not path-safe.
SUITE_NAME = "report/fixture"
SUITE_FILE = "report-fixture.json"

UNKNOWN_KEY_SCENARIO = "An unknown flag key returns the code default"

# The type-mismatch matrix: eleven Examples rows under one scenario name, one of
# which the Python SDK fails. It is the case row identity exists for.
MISMATCH_SCENARIO = "Requesting the wrong type returns the code default"

# The row that fails, spelled as the feature file spells it -- strings, because
# Gherkin has no types and "1" is not 1.
DEVIATING_ROW = {"key": "boolean-flag", "requested": "Integer", "default": "1"}

DEVIATION_ISSUE = "https://github.com/open-feature/python-sdk/issues/619"

# How Cucumber orders its statuses. A test case is as bad as its worst step, and
# this is the rule a consumer applies to derive a scenario's outcome from the
# stream -- so it is the rule these tests apply too.
SEVERITY = [
    "UNKNOWN",
    "PASSED",
    "SKIPPED",
    "PENDING",
    "UNDEFINED",
    "AMBIGUOUS",
    "FAILED",
]

_SUITE_MODULE = '''\
"""A one-fixture adoption, generated so the report can be checked end to end."""

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    InProcessControl,
    KnownDeviation,
    TckConfig,
    features_path,
)


@pytest.fixture(scope="session")
def tck_config():
    control = InProcessControl()
    return TckConfig(
        name="{name}",
        control=control,
        new_provider=control.new_provider,
        capabilities={capabilities},
        not_applicable={not_applicable},
        known_deviations={deviations},
    )


scenarios(features_path())
'''

CAPABILITIES = "{Capability.EVENTS, Capability.OBJECT, Capability.NUMERIC_COERCION}"
"""What the main generated suite declares: enough to produce a skip and a pass."""

NOT_APPLICABLE = '{Capability.STALE: "this provider has no connection to lose"}'
"""One capability the provider cannot have rather than merely does not declare."""

DEVIATIONS = (
    "(KnownDeviation("
    f'issue="{DEVIATION_ISSUE}", '
    'summary="a boolean satisfies an Integer request"),)'
)

# One scenario skipped outright and one known deviation marked xfail, so the run
# produces a skip, a pass and a failure and finishes green while the payload
# does not.
_CONFTEST_MODULE = """\
import pytest

SKIPPED = "test_an_unknown_flag_key_returns_the_code_default"
DEVIATION = "test_requesting_the_wrong_type_returns_the_code_default[boolean-flag-Integer-1]"


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name == SKIPPED:
            item.add_marker(pytest.mark.skip(reason="deliberately not run here"))
        elif item.name == DEVIATION:
            item.add_marker(pytest.mark.xfail(reason="python-sdk#619", strict=True))
"""


# A Scenario Outline whose second Examples block carries a tag of its own, which
# no canonical feature file does yet. Written here so that the one case where two
# rows of an outline are gated differently is covered.
_TAGGED_FEATURE = """\
Feature: Per-Examples tags

  Background:
    Given a stable provider

  Scenario Outline: Requesting the wrong type returns the code default
    Given a <requested>-flag with key "<key>" and a default value "<default>"
    When the flag was evaluated with details
    Then the resolved details value should be "<default>"
    And the reason should be "ERROR"
    And the error-code should be "TYPE_MISMATCH"
    And no exception should have been thrown

    Examples: ungated
      | key         | requested | default |
      | string-flag | Boolean   | false   |
      | string-flag | Integer   | 1       |

    @object
    Examples: gated behind a capability this suite does not declare
      | key         | requested | default |
      | string-flag | Float     | 0.1     |
"""

_TAGGED_SUITE = '''\
"""A suite over the feature file beside it, which tags one Examples block."""

import pathlib

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    InProcessControl,
    TckConfig,
)


@pytest.fixture(scope="session")
def tck_config():
    control = InProcessControl()
    return TckConfig(
        name="per-examples",
        control=control,
        new_provider=control.new_provider,
        capabilities={Capability.EVENTS},
    )


scenarios(str(pathlib.Path(__file__).parent))
'''


# -- reading the payload back the way a consumer would -----------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One scenario as the stream reports it, assembled from its messages."""

    uri: str
    name: str
    """The scenario name from the *AST*, so an outline's rows share it."""

    row: tuple[tuple[str, str], ...]
    """The Examples row, resolved from the pickle's AST node ids."""

    tags: frozenset[str]
    status: str
    """The worst of the test case's steps, which is Cucumber's rule."""

    setup_message: str
    """What the before-hook said, which is where a skip's reason lands."""

    step_statuses: tuple[str, ...]

    @property
    def identity(self) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        return (self.uri, self.name, self.row)


@dataclasses.dataclass(frozen=True)
class Stream:
    """A parsed Cucumber Messages stream."""

    kinds: collections.Counter[str]
    sources: dict[str, str]
    cases: list[Case]

    def named(self, name: str) -> list[Case]:
        return [case for case in self.cases if case.name == name]

    @property
    def statuses(self) -> collections.Counter[str]:
        return collections.Counter(case.status for case in self.cases)


@dataclasses.dataclass
class _Index:
    """The stream's messages, keyed the way the protocol says they relate."""

    kinds: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    sources: dict[str, str] = dataclasses.field(default_factory=dict)
    names: dict[str, str] = dataclasses.field(default_factory=dict)
    rows: dict[str, tuple[tuple[str, str], ...]] = dataclasses.field(
        default_factory=dict
    )
    pickles: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    test_cases: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    hooks: dict[str, str] = dataclasses.field(default_factory=dict)
    started: dict[str, str] = dataclasses.field(default_factory=dict)
    results: dict[str, list[tuple[str, typing.Any]]] = dataclasses.field(
        default_factory=dict
    )

    def add(self, kind: str, body: typing.Any) -> None:
        self.kinds[kind] += 1
        if kind == "source":
            self.sources[body["uri"]] = body["data"]
        elif kind == "gherkinDocument":
            _index_document(body, self.names, self.rows)
        elif kind == "pickle":
            self.pickles[body["id"]] = body
        elif kind == "testCase":
            self.test_cases[body["id"]] = body
            for step in body["testSteps"]:
                if "hookId" in step:
                    self.hooks[step["id"]] = step["hookId"]
        elif kind == "testCaseStarted":
            self.started[body["id"]] = body["testCaseId"]
        elif kind == "testStepFinished":
            self.results.setdefault(body["testCaseStartedId"], []).append(
                (body["testStepId"], body["testStepResult"])
            )


def _read_stream(path: Path) -> Stream:
    """Assemble the stream into test cases the way a consumer has to.

    Deliberately written against the protocol rather than against this package:
    a pickle's ``astNodeIds`` are followed back into the ``GherkinDocument`` to
    recover the scenario name and the Examples row, and a test case's status is
    computed as the worst of its steps. If the stream does not actually support
    those two operations, these tests fail -- which is the point.
    """
    index = _Index()
    for line in path.read_text(encoding="utf-8").splitlines():
        message = json.loads(line)
        kind = next(iter(message))
        index.add(kind, message[kind])

    cases = [
        _case(index, started_id, case_id)
        for started_id, case_id in index.started.items()
    ]
    return Stream(kinds=index.kinds, sources=index.sources, cases=cases)


def _case(index: _Index, started_id: str, case_id: str) -> Case:
    pickle = index.pickles[index.test_cases[case_id]["pickleId"]]
    ast = pickle["astNodeIds"]
    steps = index.results[started_id]
    setup: dict[str, typing.Any] = next(
        (
            result
            for step_id, result in steps
            if index.hooks.get(step_id, "").endswith("setup")
        ),
        {},
    )
    return Case(
        uri=pickle["uri"],
        name=index.names[ast[0]],
        row=index.rows.get(ast[1], ()) if len(ast) > 1 else (),
        tags=frozenset(tag["name"] for tag in pickle.get("tags", ())),
        status=max((result["status"] for _, result in steps), key=SEVERITY.index),
        setup_message=setup.get("message", ""),
        step_statuses=tuple(
            result["status"] for step_id, result in steps if step_id not in index.hooks
        ),
    )


def _index_document(
    document: dict[str, typing.Any],
    names: dict[str, str],
    rows: dict[str, tuple[tuple[str, str], ...]],
) -> None:
    def visit(children: typing.Iterable[dict[str, typing.Any]]) -> None:
        for child in children:
            if "rule" in child:
                visit(child["rule"].get("children", ()))
                continue
            scenario = child.get("scenario")
            if scenario is None:
                continue
            names[scenario["id"]] = scenario["name"]
            for examples in scenario.get("examples", ()):
                header = examples.get("tableHeader")
                if header is None:
                    continue
                headers = [cell["value"] for cell in header["cells"]]
                for row in examples.get("tableBody", ()):
                    cells = [cell["value"] for cell in row["cells"]]
                    rows[row["id"]] = tuple(zip(headers, cells, strict=True))

    feature = document.get("feature")
    if feature is not None:
        visit(feature.get("children", ()))


@dataclasses.dataclass(frozen=True)
class Run:
    """One subprocess run of the generated suite: both documents it wrote."""

    directory: Path
    result: subprocess.CompletedProcess[str]
    envelope: dict[str, typing.Any]
    stream: Stream
    stream_path: Path

    @property
    def declared(self) -> set[str]:
        return set(self.envelope["declaration"]["declared"])


# -- helpers -----------------------------------------------------------------


class _StubControl:
    """A control that says nothing about how it drove the backend."""

    @property
    def description(self) -> str:
        return "a stub"

    def prepare_scenario(self) -> None:
        return None

    def change_flag(self) -> None:
        return None


class _HttpControl(_StubControl):
    @property
    def control_api(self) -> str:
        return "http"


def _config_leaving_capabilities_to_their_default() -> TckConfig:
    """A config that does not narrow ``capabilities``, so the field default runs.

    Written out rather than routed through ``_config``, which supplies a narrow
    set of its own: the default is the whole point of this one. It needs an
    unavailable-provider factory because ``@unavailable`` is declarable and the
    default therefore declares it.
    """
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": _StubControl(),
        "new_provider": lambda: None,
        "new_unavailable_provider": lambda: None,
    }
    return TckConfig(**settings)


def _config(**overrides: typing.Any) -> TckConfig:
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": _StubControl(),
        "new_provider": lambda: None,
        "capabilities": {Capability.EVENTS},
    }
    settings.update(overrides)
    return TckConfig(**settings)


def _identity(*tags: str, name: str = "a scenario") -> ScenarioIdentity:
    return ScenarioIdentity(
        uri="features/events.feature",
        path=Path(features_path()) / "events.feature",
        name=name,
        tags=tags,
    )


def _results() -> Results:
    return Results(location="stub.ndjson", digest="sha256:" + "0" * 64)


def _examples_from_the_feature_file(feature: str, outline: str) -> list[dict[str, str]]:
    """Read an outline's Examples tables straight out of the Gherkin.

    Hand-read rather than taken from a parser, because a parser is what produced
    the values under test: asking it what it should have said would check
    nothing. It is a small reader for a small shape -- the tables in these files
    are plain pipe-delimited rows -- and it exists so that "the stream says what
    the table said" is checked against the table.
    """
    source = Path(features_path()) / f"{feature}.feature"
    lines = source.read_text(encoding="utf-8").splitlines()
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    inside = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(("Scenario:", "Scenario Outline:")):
            inside = stripped.split(":", 1)[1].strip() == outline
            headers = []
        elif not inside:
            continue
        elif stripped.startswith("Examples"):
            headers = []
        elif stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if headers:
                rows.append(dict(zip(headers, cells, strict=True)))
            else:
                headers = cells

    assert rows, f"no Examples rows found for {outline!r} in {feature}.feature"
    return rows


def _phase(outcome: str, when: str = "call", **extra: typing.Any) -> PhaseOutcome:
    return PhaseOutcome(when=when, outcome=outcome, **extra)


def _pytest(
    *arguments: str, report_dir: Path | None = None
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment.pop(REPORT_DIR_ENV, None)
    if report_dir is not None:
        environment[REPORT_DIR_ENV] = str(report_dir)
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *arguments],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def _write_suite(
    directory: Path,
    name: str = SUITE_NAME,
    capabilities: str = CAPABILITIES,
    not_applicable: str = NOT_APPLICABLE,
    deviations: bool = True,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "test_suite.py").write_text(
        _SUITE_MODULE.format(
            name=name,
            capabilities=capabilities,
            not_applicable=not_applicable,
            deviations=DEVIATIONS if deviations else "()",
        ),
        encoding="utf-8",
    )
    if deviations:
        (directory / "conftest.py").write_text(_CONFTEST_MODULE, encoding="utf-8")
    return directory


def _run_suite(
    tmp_path_factory: pytest.TempPathFactory,
    file_name: str = SUITE_FILE,
    **suite: typing.Any,
) -> Run:
    """Run one generated suite in a subprocess and read what it wrote."""
    directory = _write_suite(tmp_path_factory.mktemp("suite"), **suite)
    reports = tmp_path_factory.mktemp("reports")
    result = _pytest(str(directory), report_dir=reports)

    path = reports / file_name
    assert path.exists(), (
        f"no report at {path}; pytest exited {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    envelope = json.loads(path.read_text(encoding="utf-8"))
    stream_path = path.parent / envelope["results"]["location"]
    return Run(
        directory=directory,
        result=result,
        envelope=envelope,
        stream=_read_stream(stream_path),
        stream_path=stream_path,
    )


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """One real run of the generated suite, with a report asked for."""
    return _run_suite(tmp_path_factory)


@pytest.fixture(scope="module")
def narrow_run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """A run of a suite that leaves a whole Scenario Outline gated.

    ``@object`` is undeclared so that every row of one outline is skipped by the
    capability gate, which is the case that has to keep saying which row it
    skipped.
    """
    return _run_suite(
        tmp_path_factory,
        file_name="narrow.json",
        name="narrow",
        capabilities="{Capability.NUMERIC_COERCION}",
        not_applicable="{}",
        deviations=False,
    )


# -- the two properties that matter ------------------------------------------


def test_a_capability_skip_is_never_reported_as_passed(run: Run) -> None:
    """The rule Appendix F states, checked against the payload, not the runner."""
    gated = [case for case in run.stream.cases if case.tags - run.declared]
    assert gated, "the generated suite is meant to have scenarios behind those"

    for case in gated:
        assert case.status == "SKIPPED", case
        # Cucumber's SKIPPED is per step, so "never as passed" has to hold of
        # every step and not merely of the rolled-up verdict.
        assert set(case.step_statuses) == {"SKIPPED"}, case
        assert case.setup_message, f"a skip must say why: {case}"


def test_the_reason_for_a_gated_skip_follows_from_the_two_documents(run: Run) -> None:
    """Which is why the per-scenario reason no longer has to be transported.

    The envelope says what the provider declares; the payload says which tags
    each scenario carries and that it was skipped. A consumer with both can name
    the capability responsible without the emitter having written it down once
    per scenario, and that derivation is what the declaration exists for.
    """
    skipped = [case for case in run.stream.cases if case.status == "SKIPPED"]
    gated = [case for case in skipped if case.tags - run.declared]
    assert gated, "no skip was attributable to an undeclared capability"

    # The derivation is checked against the reason the runner actually gave: for
    # every skip the two documents attribute to a capability, that capability is
    # the one the gate named. If they disagreed, the declaration would be the
    # wrong thing to read a skip against.
    for case in gated:
        responsible = case.tags - run.declared
        assert any(tag in case.setup_message for tag in responsible), case

    # And it distinguishes: the one scenario skipped for another reason carries
    # no undeclared tag, so it is not attributed to a capability at all.
    others = [case for case in skipped if case not in gated]
    assert others, "the generated suite is meant to skip one scenario outright"
    for case in others:
        assert not case.tags - run.declared, case
        assert "capability" not in case.setup_message, case


def test_every_collected_scenario_appears_exactly_once(run: Run) -> None:
    """The property that makes the rule above checkable rather than promised.

    A test case is identified by its uri, its scenario name **and its Examples
    row**, all three recovered from the stream by following a pickle's AST node
    ids. Name alone is shared by every row of a Scenario Outline, so keying on it
    would let eleven rows of the type-mismatch matrix collapse into one and this
    test would not notice.

    Counted against pytest's own collection rather than against a number written
    down here, so that adding a scenario to the specification cannot leave this
    passing while the payload loses one.
    """
    identities = [case.identity for case in run.stream.cases]
    assert len(identities) == len(set(identities)), "a scenario is reported twice"

    collected = _pytest("--collect-only", str(run.directory))
    assert len(identities) == sum(
        1 for line in collected.stdout.splitlines() if "::test_" in line
    )


def test_the_statuses_account_for_every_scenario(run: Run) -> None:
    counts = run.stream.statuses
    assert set(counts) <= set(SEVERITY), "a status outside the protocol's own"
    assert sum(counts.values()) == len(run.stream.cases)
    # A skip, a pass and a failure all occur, which is what makes the run worth
    # asserting against at all.
    assert set(counts) == {"PASSED", "SKIPPED", "FAILED"}, counts


def test_the_payload_does_not_repeat_the_runner_summary(run: Run) -> None:
    """A known deviation is a failure in the payload even when pytest is green.

    The suite marks the one scenario the Python SDK cannot satisfy as an expected
    failure, so pytest exits zero. The provider still did not satisfy it, and a
    payload that agreed with the summary would hide exactly what the marker was
    added to keep visible. The acknowledgement goes in the envelope instead.
    """
    assert run.result.returncode == 0, run.result.stdout
    failed = [case for case in run.stream.cases if case.status == "FAILED"]
    assert len(failed) == 1
    assert failed[0].row == tuple(DEVIATING_ROW.items())

    deviations = run.envelope["knownDeviations"]
    assert [deviation["issue"] for deviation in deviations] == [DEVIATION_ISSUE]


def test_a_scenario_skipped_for_another_reason_is_still_reported(run: Run) -> None:
    """A run that chose not to execute a scenario still accounts for it.

    Skipped, and present, even though a marker skip never runs a fixture -- and
    with its own reason rather than the capability gate's, which is what tells
    the two apart now that the payload has one status for both.
    """
    matching = run.stream.named(UNKNOWN_KEY_SCENARIO)
    assert len(matching) == 1
    assert matching[0].status == "SKIPPED"
    assert "deliberately not run here" in matching[0].setup_message
    # Nothing about the provider's declaration explains this one, which is how a
    # consumer tells it from a capability skip.
    assert not matching[0].tags - run.declared


# -- which row of an outline -------------------------------------------------


def test_an_outline_row_is_identified_by_its_ast_node_id(run: Run) -> None:
    """The eleven rows of the type-mismatch matrix are told apart, and only here.

    All eleven share one scenario name, which is the feature file's name and must
    stay that way: it is what a report from Go or JavaScript carries for the same
    row. What tells them apart is the pickle's second ``astNodeIds`` entry, the
    id of the table row it was compiled from, which resolves in the
    ``GherkinDocument`` to exactly the cells the feature file wrote. That is the
    identity four implementations were each reinventing as a bespoke ``example``
    field before this format carried it.
    """
    rows = run.stream.named(MISMATCH_SCENARIO)
    expected = _examples_from_the_feature_file("errors", MISMATCH_SCENARIO)
    assert len(rows) == len(expected) == 11

    observed = [dict(case.row) for case in rows]
    assert len(observed) == len({case.row for case in rows}), "two rows collapsed"
    assert sorted(map(sorted, (row.items() for row in observed))) == sorted(
        map(sorted, (row.items() for row in expected))
    )

    # Verbatim strings, because Gherkin has no types: a "1" in a table is the
    # one-character cell the feature file contains.
    for row in observed:
        assert all(isinstance(value, str) for value in row.values()), row


def test_a_scenario_that_is_not_an_outline_has_no_row(run: Run) -> None:
    """One AST node id, so there is no row to resolve and nothing to say."""
    plain = run.stream.named(UNKNOWN_KEY_SCENARIO)
    assert len(plain) == 1
    assert plain[0].row == ()


def test_a_capability_skipped_outline_row_is_still_identified(
    narrow_run: Run,
) -> None:
    """A skipped row is exactly as ambiguous as a failed one.

    Row identity comes from the pickle rather than from the run, so it does not
    depend on the scenario having executed -- which is what lets a row the
    capability gate stopped before its first step be told apart from its siblings
    just as well as one that failed.
    """
    outline = "Requesting a structured flag as a scalar returns the code default"
    expected = _examples_from_the_feature_file("errors", outline)
    rows = narrow_run.stream.named(outline)
    assert len(rows) == len(expected)

    for case in rows:
        assert case.status == "SKIPPED", case
        assert case.row, f"a skipped outline row must say which row: {case}"
    assert sorted(map(sorted, (dict(case.row).items() for case in rows))) == sorted(
        map(sorted, (row.items() for row in expected))
    )


def test_a_row_gated_by_its_examples_block_is_the_only_one_skipped(
    tmp_path: Path,
) -> None:
    """Gherkin lets one Examples block of an outline carry its own tags.

    Two rows of one Scenario Outline can therefore differ in which capability
    gates them. Those tags are on neither the scenario, the feature nor the rule,
    and a payload built from those three would show the skipped row as carrying
    no capability -- leaving the envelope's declaration unable to explain the
    skip, which is the one derivation this format asks a consumer to make.

    No canonical feature file does this yet, so the feature file is written here.
    """
    directory = tmp_path / "suite"
    directory.mkdir(parents=True)
    (directory / "tagged.feature").write_text(_TAGGED_FEATURE, encoding="utf-8")
    (directory / "test_tagged.py").write_text(_TAGGED_SUITE, encoding="utf-8")

    reports = tmp_path / "reports"
    result = _pytest(str(directory), report_dir=reports)
    path = reports / "per-examples.json"
    assert path.exists(), f"pytest exited {result.returncode}\n{result.stdout}"

    envelope = json.loads(path.read_text(encoding="utf-8"))
    stream = _read_stream(path.parent / envelope["results"]["location"])
    by_row = {dict(case.row)["requested"]: case for case in stream.cases}

    # Every row is still reported: nothing about gating one row of an outline may
    # drop its siblings from the payload.
    assert set(by_row) == {"Boolean", "Integer", "Float"}, by_row
    assert by_row["Boolean"].status == "PASSED"
    assert by_row["Integer"].status == "PASSED"

    gated = by_row["Float"]
    assert gated.status == "SKIPPED", gated
    assert Capability.OBJECT.tag in gated.tags, gated
    assert Capability.OBJECT.tag not in envelope["declaration"]["declared"]


# -- the payload, and the envelope that points at it -------------------------


def test_the_envelope_points_at_the_payload_it_describes(run: Run) -> None:
    """Referenced rather than inlined, and covered by a digest.

    A stream carries the feature sources and is far larger than the envelope, so
    a consumer deciding whether it cares about a report should not have to fetch
    a whole run to find out -- and needs to be able to tell that what it did
    fetch is what the envelope described.
    """
    results = run.envelope["results"]
    assert results["format"] == MESSAGES_FORMAT
    # A bare file name, so the reference survives the pair being moved together.
    assert results["location"] == run.stream_path.name
    assert Path(results["location"]).parent == Path()

    digest = hashlib.sha256(run.stream_path.read_bytes()).hexdigest()
    assert results["digest"] == f"sha256:{digest}"


def test_the_payload_carries_the_source_of_every_feature_it_ran(run: Run) -> None:
    """Which is what replaced recording an asset tree hash.

    A hash said only whether two runs executed the same assets. The source says
    what the assets were, so a consumer can read the questions that were actually
    asked rather than trusting a recorded revision to stand for them.
    """
    uris = {case.uri for case in run.stream.cases}
    assert uris, "no test case named a feature file"
    assert set(run.stream.sources) == uris

    for uri, data in run.stream.sources.items():
        on_disk = Path(features_path()) / Path(uri).name
        assert data == on_disk.read_text(encoding="utf-8"), uri

    assert "assetsTree" not in run.envelope["tck"]


def test_the_payload_is_a_well_formed_messages_stream(run: Run) -> None:
    """The message types a consumer needs are all present, once each per scenario."""
    kinds = run.stream.kinds
    cases = len(run.stream.cases)
    assert kinds["meta"] == 1
    assert kinds["testRunStarted"] == 1
    assert kinds["testRunFinished"] == 1
    assert kinds["source"] == kinds["gherkinDocument"] == len(run.stream.sources)
    assert kinds["pickle"] == cases
    assert kinds["testCase"] == kinds["testCaseStarted"] == cases
    assert kinds["testCaseFinished"] == cases
    assert kinds["testStepStarted"] == kinds["testStepFinished"]


def test_the_declaration_is_an_input_not_a_summary(run: Run) -> None:
    """Which is why it cannot be derived from the payload and is stated here.

    Declared and not-applicable are disjoint and mean different things -- a
    choice against a capability, and an impossibility -- and the payload can
    express neither, because a skip in it says only that the question was not
    put to this provider.
    """
    declaration = run.envelope["declaration"]
    assert declaration["declared"] == [
        Capability.EVENTS.tag,
        Capability.NUMERIC_COERCION.tag,
        Capability.OBJECT.tag,
    ]
    assert declaration["notApplicable"] == {
        Capability.STALE.tag: "this provider has no connection to lose"
    }
    assert Capability.STALE.tag not in declaration["declared"]


def test_the_provider_and_its_configuration_are_reported_separately(run: Run) -> None:
    assert run.envelope["provider"]["name"] == "In-Memory Provider"
    assert run.envelope["provider"]["configuration"] == SUITE_NAME
    assert run.envelope["provider"]["language"] == "python"


def test_the_envelope_names_what_ran_it(run: Run) -> None:
    assert run.envelope["schemaVersion"] == "1"
    assert (
        run.envelope["tck"]["implementation"]
        == "python-sdk-contrib/tools/openfeature-tck"
    )
    assert run.envelope["sdk"]["name"] == "openfeature-sdk"
    assert run.envelope["sdk"]["version"]
    assert len(run.envelope["tck"]["specRevision"]) >= 7
    assert run.envelope["backend"]["controlApi"] == "in-process"


def test_the_envelope_carries_no_results_of_its_own(run: Run) -> None:
    """The fields Cucumber Messages made redundant, checked to be gone.

    Not a shape test for its own sake: while both existed there were two places
    for the same fact to disagree, which is the whole reason the per-scenario
    list was deleted rather than kept alongside the payload.
    """
    assert "scenarios" not in run.envelope
    assert "capabilities" not in run.envelope


def test_the_spec_revision_comes_from_the_build() -> None:
    """Generated beside the assets, because the submodule is not in the wheel."""
    assert len(spec_revision()) >= 7


# -- opting in ---------------------------------------------------------------


def test_no_report_is_written_without_the_environment_variable(
    tmp_path: Path,
) -> None:
    """The default, and not an error: emitting is a property of the run."""
    directory = _write_suite(tmp_path / "suite")
    result = _pytest(str(directory), report_dir=None)
    assert result.returncode == 0, result.stdout
    assert "report written" not in result.stdout
    assert not list(tmp_path.rglob("*.json"))
    assert not list(tmp_path.rglob("*.ndjson"))


def test_a_report_that_cannot_be_written_fails_the_run(tmp_path: Path) -> None:
    """Loudly, because a pipeline that silently got no report serves a stale one.

    The destination is placed under a regular file, which no platform will let
    ``mkdir`` turn into a directory. The run itself passes, so a non-zero exit
    can only have come from the failure to write.
    """
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    directory = _write_suite(tmp_path / "suite")
    result = _pytest(str(directory), report_dir=blocker / "reports")
    assert "could not write the conformance report" in result.stdout
    assert result.returncode != 0


# -- assembling the documents ------------------------------------------------


def test_a_failure_is_not_revised_away_by_a_later_phase() -> None:
    """A scenario whose steps passed and whose teardown blew up is a failure."""
    run = scenario_run(
        _identity(),
        [
            _phase("passed", when="setup"),
            _phase("passed", when="call"),
            _phase("failed", when="teardown", message="teardown exploded"),
        ],
        [StepRun(status=Status.passed)],
    )
    assert run.status is Status.failed
    assert run.message == "teardown exploded"


def test_a_verdict_no_step_accounts_for_reaches_the_stream_anyway() -> None:
    """A strict xfail that passes fails a scenario every step of which passed.

    A consumer reads a test case's outcome as the worst of its steps, so a
    verdict left only in this package's own head would be lost on the way out.
    It is attached to the after-hook, which is where a test case failing outside
    its own steps belongs.
    """
    run = scenario_run(
        _identity(),
        [
            _phase("passed", when="setup"),
            _phase("failed", when="call", message="[XPASS(strict)] python-sdk#619"),
            _phase("passed", when="teardown"),
        ],
        [StepRun(status=Status.passed)],
    )
    assert run.status is Status.failed
    assert run.teardown is not None
    assert run.teardown.status is Status.passed, "the phase itself did pass"

    # The stream is where the discrepancy has to be resolved, and it is:
    # `_step_runs` upgrades the after-hook when nothing else carries the verdict.
    steps = _step_runs(_Pickle(id="p", step_ids=("s",), payload={}), run)
    worst = max((step.status.value for step in steps), key=SEVERITY.index)
    assert worst == Status.failed.value
    assert "XPASS(strict)" in steps[-1].message


def test_a_gated_skip_is_skipped_for_every_step() -> None:
    """The gate stops a scenario in setup, so no step of it ran."""
    run = scenario_run(
        _identity("@stale"),
        [_phase("skipped", when="setup", message="provider does not declare @stale")],
        [],
    )
    assert run.status is Status.skipped
    assert run.setup is not None
    assert run.setup.message == "provider does not declare @stale"


def test_the_declaration_reports_what_the_configuration_declares() -> None:
    suite = SuiteReport(config=_config(capabilities={Capability.EVENTS}))
    declaration = suite.build(_results())["declaration"]
    assert declaration["declared"] == [Capability.EVENTS.tag]
    assert "notApplicable" not in declaration


def test_a_not_applicable_capability_is_reported_with_its_reason() -> None:
    """Impossible is not the same claim as undeclared, and the report keeps both."""
    suite = SuiteReport(
        config=_config(
            capabilities={Capability.EVENTS},
            not_applicable={Capability.NUMERIC_COERCION: "no integer type"},
        )
    )
    declaration = suite.build(_results())["declaration"]
    assert declaration["notApplicable"] == {
        Capability.NUMERIC_COERCION.tag: "no integer type"
    }


def test_a_capability_cannot_be_both_declared_and_impossible() -> None:
    with pytest.raises(ValueError, match="both claim @events"):
        _config(
            capabilities={Capability.EVENTS},
            not_applicable={Capability.EVENTS: "a reason"},
        )


def test_a_not_applicable_capability_must_say_why() -> None:
    with pytest.raises(ValueError, match="no reason for @stale"):
        _config(
            capabilities={Capability.EVENTS}, not_applicable={Capability.STALE: " "}
        )


def test_a_reserved_capability_cannot_be_declared() -> None:
    """A tag no scenario carries is a claim nothing can check, so it is refused.

    Refused at construction rather than dropped at emission time, for the same
    reason a capability claimed as both declared and impossible is: the adopter
    wrote it down and meant something by it, and a config silently different
    from the one they wrote is worse than one that will not build. This is also
    where their own code is still on the stack.
    """
    for reserved in RESERVED_CAPABILITIES:
        with pytest.raises(ValueError, match=f"reserved capabilities {reserved.tag}"):
            _config(capabilities={Capability.EVENTS, reserved})
        with pytest.raises(ValueError, match=f"reserved capabilities {reserved.tag}"):
            _config(
                capabilities={Capability.EVENTS},
                not_applicable={reserved: "no scenario asks"},
            )


def test_a_reserved_capability_cannot_reach_the_declaration() -> None:
    """Including by the route that actually caused it: declaring everything.

    The schema forbids a capability no executed scenario carries from appearing
    in ``declaration.declared``, because such a tag cannot produce a skip and so
    plays no part in reading the results -- it only invites a reader to believe
    something was verified when nothing examined it. A real report from another
    implementation asserts ``@targeting`` and ``@caching`` for exactly this
    reason: that adoption declares "every capability except X" and collected the
    reserved tags on the way past. So the default is the declarable set rather
    than the whole enum.
    """
    declared = SuiteReport(
        config=_config_leaving_capabilities_to_their_default()
    ).build(_results())["declaration"]["declared"]

    assert declared == sorted(capability.tag for capability in DECLARABLE_CAPABILITIES)
    assert RESERVED_CAPABILITIES, "the rule is vacuous if nothing is reserved"
    for reserved in RESERVED_CAPABILITIES:
        assert reserved.tag not in declared


def test_known_deviations_are_omitted_rather_than_emitted_empty() -> None:
    """Stating none is a claim; omitting the field is silence."""
    assert "knownDeviations" not in SuiteReport(config=_config()).build(_results())

    acknowledged = SuiteReport(
        config=_config(
            known_deviations=(
                KnownDeviation(
                    issue=DEVIATION_ISSUE,
                    summary="a boolean satisfies an Integer request",
                    capability=Capability.NUMERIC_COERCION,
                ),
            )
        )
    ).build(_results())["knownDeviations"]
    assert acknowledged == [
        {
            "issue": DEVIATION_ISSUE,
            "summary": "a boolean satisfies an Integer request",
            "capability": Capability.NUMERIC_COERCION.tag,
        }
    ]


def test_the_provider_name_falls_back_to_the_suite_name() -> None:
    """A suite whose every scenario was skipped never saw a provider.

    Reporting the suite name is more useful than the empty string the schema
    would reject.
    """
    envelope = SuiteReport(config=_config()).build(_results())
    assert envelope["provider"]["name"] == "stub"


def test_the_control_api_is_omitted_when_the_control_does_not_say() -> None:
    plain = SuiteReport(config=_config()).build(_results())
    assert "controlApi" not in plain["backend"]
    http = SuiteReport(config=_config(control=_HttpControl())).build(_results())
    assert http["backend"]["controlApi"] == "http"


def test_control_api_ignores_a_value_the_schema_would_reject() -> None:
    class Odd(_StubControl):
        control_api = "carrier pigeon"

    assert control_api_of(Odd()) == ""


@pytest.mark.parametrize(
    ("suite_name", "expected"),
    [
        ("in-memory", "in-memory"),
        ("flagd/rpc", "flagd-rpc"),
        ("../escape", "escape"),
        ("...", "report"),
    ],
)
def test_a_suite_name_cannot_write_outside_its_directory(
    suite_name: str, expected: str
) -> None:
    """Suite names are chosen to read well in a failure message, not to be paths."""
    assert envelope_file_name(suite_name) == f"{expected}.json"
    assert stream_file_name(suite_name) == f"{expected}.ndjson"


def test_only_tags_the_schema_accepts_are_carried() -> None:
    assert normalise_tags({"events", "Not A Tag", "stale"}) == ("@events", "@stale")


def test_a_feature_uri_is_slash_separated_on_every_platform() -> None:
    """The same string has to appear in the source, the document and the pickles.

    pytest-bdd builds it with ``os.path.join``, so on Windows it arrives
    backslash-separated -- and a report emitted there would otherwise not be
    comparable with one emitted on Linux.
    """
    assert feature_uri("features/errors.feature") == "features/errors.feature"
    assert feature_uri(os.path.join("features", "errors.feature")) == (
        "features/errors.feature"
    )


# -- classifying one phase ---------------------------------------------------


def test_an_expected_failure_is_still_a_failure() -> None:
    """An xfail marker records a known deviation; it does not excuse one."""
    status, message = classify_phase(
        _phase("skipped", xfail_reason="the SDK coerces a bool to an int")
    )
    assert status is Status.failed
    assert "the SDK coerces a bool to an int" in message


def test_a_phase_that_merely_worked_says_nothing_in_particular() -> None:
    assert classify_phase(_phase("passed", when="setup")) == (Status.passed, "")
    assert classify_phase(_phase("passed", when="call")) == (Status.passed, "")


def test_a_skip_keeps_its_reason() -> None:
    assert classify_phase(
        _phase("skipped", when="setup", message="provider does not declare @stale")
    ) == (Status.skipped, "provider does not declare @stale")
    assert classify_phase(_phase("skipped", when="setup")) == (
        Status.skipped,
        "skipped",
    )
