"""That a run which executed less than the canonical set says so, and publishes nothing.

The capability gate rules out the loud way a conformance suite can go green on
scenarios it did not run: an undeclared capability is reported as skipped, with
its reason. Nothing ruled out the quiet way, where the scenarios were never
collected at all. ``-k``, ``-m``, ``--deselect``, a test module that stopped
calling ``scenarios()`` on the canonical path -- each runs less of the suite, and
none of them is an error to pytest.

Go measured the consequence: ``-run`` on a single scenario passed green and
emitted a well-formed report covering one of twenty-nine canonical scenarios.
Nothing in that document said so, and nothing reading it could have known.

So the properties here are about what a report is allowed to be written from.
Everything that has to be checked end to end is, because the question is about a
whole pytest session rather than about what a function returns.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import typing
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import (
    EXTENSIONS_DIRECTORY,
    PARTIAL_ENV,
    REPORT_DIR_ENV,
)
from openfeature.contrib.tools.tck.canonical import (
    canonical_scenarios,
    describe,
    missing_canonical,
    partial_run_allowed,
)
from openfeature.contrib.tools.tck.extensions import is_canonical_uri
from openfeature.contrib.tools.tck.messages import (
    ScenarioIdentity,
    ScenarioRun,
)

SUITE_NAME = "guarded"

_SUITE_MODULE = '''\
"""A one-fixture adoption, generated so a partial run can be checked end to end."""

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    InProcessControl,
    TckConfig,
    feature_paths,
)


@pytest.fixture(scope="session")
def tck_config():
    control = InProcessControl()
    return TckConfig(
        name="guarded",
        control=control,
        new_provider=control.new_provider,
        capabilities={Capability.EVENTS, Capability.OBJECT},
    )


scenarios(*feature_paths())
'''

_CONFTEST_MODULE = """\
import pytest

DEVIATION = "[boolean-flag-Integer-1]"


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name.endswith(DEVIATION):
            item.add_marker(pytest.mark.xfail(reason="python-sdk#619"))
"""

# Three scenarios of an adopter's own, so that a run which drops one canonical
# scenario still executes more scenarios than the canonical set contains. The
# count is what makes "an extension cannot close a gap" checkable rather than
# asserted.
_VENDOR_FEATURE = """\
Feature: Vendor rules

  Background:
    Given a stable provider

  Scenario: A vendor rule resolves
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"

  Scenario: A vendor rule resolves again
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"

  Scenario: And once more
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"
"""

# The canonical scenario the filtered runs below leave out. Named rather than
# counted, so a change to the canonical assets cannot leave these passing while
# they select nothing.
EXCLUDED_SELECTOR = "unknown_flag_key"
EXCLUDED_SCENARIO = "An unknown flag key returns the code default"


@dataclasses.dataclass(frozen=True)
class Run:
    """One subprocess run of the generated adoption."""

    reports: Path
    result: subprocess.CompletedProcess[str]

    @property
    def stdout(self) -> str:
        return self.result.stdout

    @property
    def envelopes(self) -> list[Path]:
        return sorted(self.reports.glob("*.json"))


def _run(
    tmp_path: Path,
    *arguments: str,
    partial: bool = False,
    extension: bool = False,
) -> Run:
    directory = tmp_path / "adoption"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "test_guarded.py").write_text(_SUITE_MODULE, encoding="utf-8")
    (directory / "conftest.py").write_text(_CONFTEST_MODULE, encoding="utf-8")
    if extension:
        features = directory / EXTENSIONS_DIRECTORY
        features.mkdir(parents=True, exist_ok=True)
        (features / "vendor.feature").write_text(_VENDOR_FEATURE, encoding="utf-8")

    reports = tmp_path / "reports"
    environment = dict(os.environ)
    environment[REPORT_DIR_ENV] = str(reports)
    if partial:
        environment[PARTIAL_ENV] = "1"
    else:
        environment.pop(PARTIAL_ENV, None)

    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(directory),
            *arguments,
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    return Run(reports=reports, result=result)


def _identity(uri: str, name: str, path: Path) -> ScenarioIdentity:
    return ScenarioIdentity(uri=uri, path=path, name=name, tags=())


# -- a run that executed the whole set ---------------------------------------


@pytest.fixture(scope="module")
def complete(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """The unfiltered run, which is what everything else is measured against."""
    return _run(tmp_path_factory.mktemp("complete"), extension=True)


def test_the_whole_canonical_set_still_writes_a_report(complete: Run) -> None:
    """Including the scenarios the capability gate skipped.

    A gated skip *ran*: it was asked, and the report accounts for it with a
    reason. Treating it as missing would make the guard contradict the one rule
    the suite is built around.
    """
    assert complete.result.returncode == 0, complete.stdout
    assert [path.name for path in complete.envelopes] == [f"{SUITE_NAME}.json"]
    assert "canonical scenarios did not run" not in complete.stdout
    # This adoption declares neither @stale nor @lifecycle, so some canonical
    # scenarios were skipped -- which is the case being asserted about.
    assert " skipped" in complete.stdout


# -- and one that did not ----------------------------------------------------


def test_a_filtered_run_fails_and_writes_no_report(tmp_path: Path) -> None:
    """The Go hazard, at the point it would have produced the document.

    A well-formed report covering one scenario of twenty-nine is worse than no
    report, because nothing in it says which twenty-eight were never asked.
    """
    run = _run(tmp_path, "-k", EXCLUDED_SELECTOR)

    assert run.result.returncode != 0, run.stdout
    assert "of 29 canonical scenarios did not run" in run.stdout
    assert not run.envelopes, "a partial run must publish nothing"
    assert not list(run.reports.glob("*.ndjson"))
    # The message names scenarios rather than only counting them, and says how
    # to filter deliberately.
    assert EXCLUDED_SCENARIO not in run.stdout, "that one is the scenario that ran"
    assert PARTIAL_ENV in run.stdout


def test_acknowledging_a_partial_run_does_not_make_it_publishable(
    tmp_path: Path,
) -> None:
    """``PROVIDER_TCK_PARTIAL`` buys a green run, never a document.

    Someone working on one scenario should not have to fight the guard; nobody
    should be able to turn a partial run into a conformance claim. Those are
    different requests, and only the first is granted. Java's TCK spells the
    same escape hatch the same way.
    """
    run = _run(tmp_path, "-k", EXCLUDED_SELECTOR, partial=True)

    assert run.result.returncode == 0, run.stdout
    assert "canonical scenarios did not run" in run.stdout
    assert f"{PARTIAL_ENV} is set" in run.stdout
    assert not run.envelopes, "acknowledged or not, it is not a conformance run"


def test_an_extension_cannot_close_a_gap(tmp_path: Path) -> None:
    """Three extension scenarios do not make up for one canonical one.

    The adoption below runs thirty-one scenarios where the canonical set has
    twenty-nine, and is still one short: an adopter's scenarios are theirs, and
    counting them towards the specification's set would let any gap be filled by
    adding a feature file.
    """
    run = _run(tmp_path, "-k", f"not {EXCLUDED_SELECTOR}", extension=True)

    assert run.result.returncode != 0, run.stdout
    assert "1 of 29 canonical scenarios did not run" in run.stdout
    assert f"features/errors.feature: {EXCLUDED_SCENARIO}" in run.stdout
    assert not run.envelopes


# -- what the canonical set is -----------------------------------------------


def test_the_canonical_set_is_read_from_the_packaged_assets() -> None:
    """One entry per Scenario Outline row, which is what a runner generates."""
    scenarios = canonical_scenarios()
    assert len(scenarios) == 29
    assert all(is_canonical_uri(uri) for uri, _, _ in scenarios)
    # An outline contributes rows, not a single templated entry.
    assert any(row for _, _, row in scenarios)


def test_a_run_of_nothing_is_missing_everything() -> None:
    assert set(missing_canonical([])) == canonical_scenarios()


def test_an_extension_run_is_neither_counted_nor_blamed(tmp_path: Path) -> None:
    """Matched by path rather than by uri.

    The uri is derived, and a check that rested on the same derivation it exists
    to corroborate would be checking its own arithmetic.
    """
    vendor = ScenarioRun(
        identity=_identity(
            "extensions/vendor.feature",
            "A vendor rule resolves",
            tmp_path / EXTENSIONS_DIRECTORY / "vendor.feature",
        )
    )
    # Even one that claims a canonical uri outright -- which the report refuses
    # separately -- cannot reduce the missing set.
    impostor = ScenarioRun(
        identity=_identity(
            "features/errors.feature",
            EXCLUDED_SCENARIO,
            tmp_path / "features" / "errors.feature",
        )
    )
    assert set(missing_canonical([vendor, impostor])) == canonical_scenarios()


def test_a_missing_scenario_is_described_by_its_row() -> None:
    assert describe(("features/x.feature", "A scenario", ())) == (
        "features/x.feature: A scenario"
    )
    assert describe(("features/x.feature", "An outline", (("key", "a"),))) == (
        "features/x.feature: An outline [key=a]"
    )


@pytest.mark.parametrize(
    ("value", "allowed"),
    [("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True)],
)
def test_the_acknowledgement_is_read_generously(value: str, allowed: bool) -> None:
    assert partial_run_allowed({PARTIAL_ENV: value}) is allowed


@pytest.mark.parametrize("value", ["", "0", "false", "no", " ", "maybe"])
def test_anything_else_is_not_an_acknowledgement(value: str) -> None:
    """Including a typo: the default has to be the safe one."""
    assert partial_run_allowed({PARTIAL_ENV: value}) is False
    assert partial_run_allowed({}) is False


def test_the_envelope_of_a_complete_run_is_unchanged(complete: Run) -> None:
    """The guard withholds a report; it does not add anything to one."""
    envelope: dict[str, typing.Any] = json.loads(
        complete.envelopes[0].read_text(encoding="utf-8")
    )
    assert set(envelope) == {
        "schemaVersion",
        "provider",
        "sdk",
        "tck",
        "backend",
        "declaration",
        "results",
    }
