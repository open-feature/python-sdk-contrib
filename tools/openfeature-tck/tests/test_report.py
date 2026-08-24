"""What the conformance report must never do.

The report exists because a runner's summary cannot be checked by anything
downstream. So the tests that matter here are not about JSON shape; they are
about the two properties a consumer is entitled to assume, neither of which is
guaranteed by the code that happens to assemble the document:

* a scenario skipped for an undeclared capability is never reported as passed,
  and carries the reason it was skipped;
* every scenario the run collected appears exactly once, which is what makes the
  first property checkable rather than merely asserted -- a document that quietly
  dropped what it skipped would satisfy the letter of it and still mislead.

Both are checked against a real pytest session in a subprocess, because both are
properties of how the suite runs rather than of how the document is assembled.
That session is also the only place all four outcomes occur together, and the
only place the document can be seen to disagree with the runner's summary --
which it does, deliberately, for a known deviation.
"""

from __future__ import annotations

import collections
import dataclasses
import json
import os
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import Capability, TckConfig
from openfeature.contrib.tools.tck.emitter import classify_phase
from openfeature.contrib.tools.tck.report import (
    REPORT_DIR_ENV,
    Outcome,
    PhaseOutcome,
    ScenarioIdentity,
    SuiteReport,
    control_api_of,
    normalise_tags,
    report_file_name,
    spec_identity,
)

OUTCOMES = {outcome.value for outcome in Outcome}

# The generated suite's name is deliberately not path-safe.
SUITE_NAME = "report/fixture"
SUITE_FILE = "report-fixture.json"

UNKNOWN_KEY_SCENARIO = "An unknown flag key returns the code default"

_SUITE_MODULE = '''\
"""A one-fixture adoption, generated so the report can be checked end to end."""

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    InProcessControl,
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
        capabilities={{
            Capability.EVENTS,
            Capability.OBJECT,
            Capability.STRICT_NUMERIC_TYPING,
        }},
    )


scenarios(features_path())
'''

# One scenario skipped outright and one known deviation marked xfail, so the run
# produces all four outcomes and finishes green while the document does not.
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


@dataclasses.dataclass(frozen=True)
class Run:
    """One subprocess run of the generated suite."""

    directory: Path
    result: subprocess.CompletedProcess[str]
    document: dict[str, typing.Any]

    @property
    def scenarios(self) -> list[dict[str, typing.Any]]:
        scenarios: list[dict[str, typing.Any]] = self.document["scenarios"]
        return scenarios


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


def _config(**overrides: typing.Any) -> TckConfig:
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": _StubControl(),
        "new_provider": lambda: None,
        "capabilities": {Capability.EVENTS},
    }
    settings.update(overrides)
    return TckConfig(**settings)


def _identity(*tags: str) -> ScenarioIdentity:
    return ScenarioIdentity(feature="events", name="a scenario", tags=tags)


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


def _write_suite(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "test_suite.py").write_text(
        _SUITE_MODULE.format(name=SUITE_NAME), encoding="utf-8"
    )
    (directory / "conftest.py").write_text(_CONFTEST_MODULE, encoding="utf-8")
    return directory


@pytest.fixture(scope="module")
def run(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """One real run of the generated suite, with a report asked for."""
    directory = _write_suite(tmp_path_factory.mktemp("suite"))
    reports = tmp_path_factory.mktemp("reports")
    result = _pytest(str(directory), report_dir=reports)

    path = reports / SUITE_FILE
    assert path.exists(), (
        f"no report at {path}; pytest exited {result.returncode}\n"
        f"{result.stdout}\n{result.stderr}"
    )
    return Run(
        directory=directory,
        result=result,
        document=json.loads(path.read_text(encoding="utf-8")),
    )


# -- the two properties that matter ------------------------------------------


def test_a_capability_skip_is_never_reported_as_passed(run: Run) -> None:
    """The rule Appendix F states, checked against the document, not the runner."""
    undeclared = {
        tag
        for tag, result in run.document["capabilities"].items()
        if result["state"] == Outcome.NOT_DECLARED.value
    }
    assert undeclared, "the generated suite is meant to leave capabilities undeclared"

    gated = [s for s in run.scenarios if undeclared & set(s.get("tags", ()))]
    assert gated, "the generated suite is meant to have scenarios behind those"
    for scenario in gated:
        assert scenario["outcome"] == Outcome.NOT_DECLARED.value, scenario
        assert scenario.get("reason"), f"a skip must say why: {scenario}"


def test_every_collected_scenario_appears_exactly_once(run: Run) -> None:
    """The property that makes the rule above checkable rather than promised.

    Counted against pytest's own collection rather than against a number written
    down here, so that adding a scenario to the specification cannot leave this
    passing while the report loses one.
    """
    names = [(s["feature"], s["name"]) for s in run.scenarios]
    assert len(names) == len(set(names)), "a scenario is reported twice"

    collected = _pytest("--collect-only", str(run.directory))
    assert len(names) == sum(
        1 for line in collected.stdout.splitlines() if "::test_" in line
    )


def test_the_outcomes_account_for_every_scenario(run: Run) -> None:
    counts = collections.Counter(s["outcome"] for s in run.scenarios)
    assert set(counts) <= OUTCOMES, "an outcome outside the four the schema allows"
    assert sum(counts.values()) == len(run.scenarios)
    # All four occur, which is what makes the distinctions worth drawing.
    assert set(counts) == OUTCOMES, counts


def test_the_document_does_not_repeat_the_runner_summary(run: Run) -> None:
    """A known deviation is a failure in the report even when pytest finishes green.

    The suite marks the one scenario the Python SDK cannot satisfy as an expected
    failure, so pytest exits zero. The provider still did not satisfy it, and a
    document that agreed with the summary would hide exactly what the marker was
    added to keep visible.
    """
    assert run.result.returncode == 0, run.result.stdout
    failed = [s for s in run.scenarios if s["outcome"] == Outcome.FAILED.value]
    assert len(failed) == 1
    assert "python-sdk#619" in failed[0]["reason"]


def test_a_scenario_skipped_for_another_reason_is_not_a_missing_capability(
    run: Run,
) -> None:
    """A run that chose not to execute a scenario is a different fact from a gap.

    ``not-applicable`` rather than ``not-declared``, because nothing about the
    provider's declared capabilities kept it from running -- and it appears at
    all, even though a marker skip never runs a fixture.
    """
    matching = [s for s in run.scenarios if s["name"] == UNKNOWN_KEY_SCENARIO]
    assert len(matching) == 1
    assert matching[0]["outcome"] == Outcome.NOT_APPLICABLE.value
    assert "deliberately not run here" in matching[0]["reason"]


# -- identity ----------------------------------------------------------------


def test_the_provider_and_its_configuration_are_reported_separately(run: Run) -> None:
    assert run.document["provider"]["name"] == "In-Memory Provider"
    assert run.document["provider"]["configuration"] == SUITE_NAME
    assert run.document["provider"]["language"] == "python"


def test_the_report_names_what_ran_it(run: Run) -> None:
    assert run.document["schemaVersion"] == "1"
    assert (
        run.document["tck"]["implementation"]
        == "python-sdk-contrib/tools/openfeature-tck"
    )
    assert run.document["sdk"]["name"] == "openfeature-sdk"
    assert run.document["sdk"]["version"]
    assert len(run.document["tck"]["specRevision"]) >= 7
    assert run.document["backend"]["controlApi"] == "in-process"


def test_the_spec_revision_comes_from_the_build() -> None:
    """Generated beside the assets, because the submodule is not in the wheel."""
    revision, tree = spec_identity()
    assert len(revision) >= 7
    assert tree == "" or len(tree) == 40


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


# -- assembling the document -------------------------------------------------


def test_a_failure_is_not_revised_away_by_a_later_phase() -> None:
    """A scenario whose steps passed and whose teardown blew up is a failure."""
    suite = SuiteReport(config=_config())
    identity = _identity()
    suite.set_outcome("node", identity, Outcome.FAILED, "teardown exploded")
    suite.set_outcome("node", identity, Outcome.PASSED)
    assert suite.records["node"].outcome is Outcome.FAILED
    assert suite.records["node"].reason == "teardown exploded"


def test_an_undeclared_capability_is_reported_with_a_reason() -> None:
    document = SuiteReport(config=_config()).build()
    assert document["capabilities"]["@events"] == {"state": Outcome.PASSED.value}
    stale = document["capabilities"]["@stale"]
    assert stale["state"] == Outcome.NOT_DECLARED.value
    assert "@stale" in stale["reason"]


def test_a_capability_whose_scenario_failed_is_not_reported_as_passed() -> None:
    suite = SuiteReport(config=_config())
    suite.set_outcome("node", _identity("@events"), Outcome.FAILED, "boom")
    assert suite.build()["capabilities"]["@events"]["state"] == Outcome.FAILED.value


def test_the_provider_name_falls_back_to_the_suite_name() -> None:
    """A suite whose every scenario was skipped never saw a provider.

    Reporting the suite name is more useful than the empty string the schema
    would reject.
    """
    assert SuiteReport(config=_config()).build()["provider"]["name"] == "stub"


def test_the_control_api_is_omitted_when_the_control_does_not_say() -> None:
    assert "controlApi" not in SuiteReport(config=_config()).build()["backend"]
    http = SuiteReport(config=_config(control=_HttpControl())).build()
    assert http["backend"]["controlApi"] == "http"


def test_control_api_ignores_a_value_the_schema_would_reject() -> None:
    class Odd(_StubControl):
        control_api = "carrier pigeon"

    assert control_api_of(Odd()) == ""


@pytest.mark.parametrize(
    ("suite_name", "expected"),
    [
        ("in-memory", "in-memory.json"),
        ("flagd/rpc", "flagd-rpc.json"),
        ("../escape", "escape.json"),
        ("...", "report.json"),
    ],
)
def test_a_suite_name_cannot_write_outside_its_directory(
    suite_name: str, expected: str
) -> None:
    """Suite names are chosen to read well in a failure message, not to be paths."""
    assert report_file_name(suite_name) == expected


def test_only_tags_the_schema_accepts_are_carried() -> None:
    assert normalise_tags({"events", "Not A Tag", "stale"}) == ("@events", "@stale")


# -- classifying one phase ---------------------------------------------------


def test_an_expected_failure_is_still_a_failure() -> None:
    """An xfail marker records a known deviation; it does not excuse one."""
    classified = classify_phase(
        _phase("skipped", xfail_reason="the SDK coerces a bool to an int"),
        _identity(),
        _config(),
    )
    assert classified is not None
    outcome, reason = classified
    assert outcome is Outcome.FAILED
    assert "the SDK coerces a bool to an int" in reason


def test_a_phase_that_merely_worked_says_nothing() -> None:
    assert (
        classify_phase(_phase("passed", when="setup"), _identity(), _config()) is None
    )
    assert classify_phase(_phase("passed", when="call"), _identity(), _config()) == (
        Outcome.PASSED,
        "",
    )


def test_a_gated_skip_and_an_ungated_skip_are_different_outcomes() -> None:
    config = _config(capabilities={Capability.EVENTS})
    gated = classify_phase(_phase("skipped", when="setup"), _identity("@stale"), config)
    assert gated == (Outcome.NOT_DECLARED, "provider does not declare @stale")

    ungated = classify_phase(
        _phase("skipped", when="setup"), _identity("@events"), config
    )
    assert ungated == (Outcome.NOT_APPLICABLE, "skipped")
