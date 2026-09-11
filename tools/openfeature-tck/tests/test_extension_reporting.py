"""What a conformance report says about an adopter's own scenarios.

That an extension *runs* inside the canonical suite, and cannot take a canonical
feature file's identity, is checked in ``test_extensions`` without a report in
sight. What is left is what the report does with it, and it is the half a
consumer actually reads:

* an extension scenario appears in the same suite's report as the canonical ones,
  which is not presentational -- a report is written per ``TckConfig``, so
  appearing in one is appearing in the same provider registration;
* it appears under the ``extensions/`` uri prefix and never the reserved
  ``features/`` one, which is the only thing telling a consumer whose question a
  scenario was;
* an adoption with no extension writes the report it wrote before, field for
  field;
* and the two cases the uri derivation cannot rule out produce **no report at
  all** rather than a plausible one.

The last is where reporting adds a rule rather than a field. A document that
presents an adopter's feature file as the specification's -- or one file's
scenarios against another file's source -- is worse than no document, because it
is the one thing a consumer cannot check from the outside. Java measured the
loud form of it: a same-named feature file in a second classpath root silently
*replaced* the canonical one, and the run went green having asked the adopter's
questions.

All of it is read back from the emitted documents the way a consumer reads them,
against real pytest sessions in subprocesses, because every property is about
what a whole session wrote.
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

from openfeature.contrib.tools.tck import (
    EXTENSIONS_DIRECTORY,
    REPORT_DIR_ENV,
    features_path,
)
from openfeature.contrib.tools.tck.extensions import is_canonical_uri

CANONICAL_FEATURE = "errors.feature"
"""The canonical file the shadowing fixture copies, chosen because it is the one
whose scenarios an extension could most plausibly want to restate."""

VENDOR_URI = "extensions/vendor.feature"
VENDOR_SCENARIO = "A vendor rule resolves through the suite's own provider"


# -- the generated adoption --------------------------------------------------

_SUITE_MODULE = '''\
"""A one-fixture adoption, generated so extensions can be checked end to end."""

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    InProcessControl,
    TckConfig,
    feature_paths,
    features_path,
)


@pytest.fixture(scope="session")
def tck_config():
    control = InProcessControl()
    return TckConfig(
        name="{name}",
        control=control,
        new_provider=control.new_provider,
        capabilities={{Capability.EVENTS, Capability.OBJECT}},
    )


scenarios({call})
'''

_EXTENSION_CALL = "*feature_paths()"
_CANONICAL_CALL = "features_path()"

# The step the adopter writes, in the adopter's own conftest.py and nowhere else.
# It asks the TCK's own per-scenario state what provider this scenario is running
# against, which is what makes "the same backend lifecycle" checkable rather than
# asserted: a second harness would have a second provider, or none.
_CONFTEST_MODULE = """\
import pytest
from pytest_bdd import then

from openfeature.contrib.tools.tck import TckState

DEVIATION = "[boolean-flag-Integer-1]"


@then("the vendor rule ran against the provider the suite registered")
def vendor_rule_ran(tck_state: TckState) -> None:
    assert tck_state.client is not None, "no provider was registered"
    assert tck_state.provider_name == "In-Memory Provider", tck_state.provider_name


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name.endswith(DEVIATION):
            item.add_marker(pytest.mark.xfail(reason="python-sdk#619"))
"""

# Deliberately reuses the canonical step vocabulary and adds exactly one step of
# its own, which is the shape an adopter's feature file actually takes.
_VENDOR_FEATURE = """\
Feature: Vendor rules

  Background:
    Given a stable provider

  Scenario: A vendor rule resolves through the suite's own provider
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"
    And the vendor rule ran against the provider the suite registered
"""

# The same Feature name and the same Scenario name as the file above, with a
# different step list -- so that a run reporting one against the other's source
# would be wrong in a way nothing downstream could notice.
_NESTED_FEATURE = """\
Feature: Vendor rules

  Background:
    Given a stable provider

  Scenario: A vendor rule resolves through the suite's own provider
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"
"""

# An adopter's own directory named `features`, which is the one way a
# non-canonical file can still reach the reserved prefix. Its scenario is
# deliberately trivial: the point is the file name, not what it asks.
_RESERVED_FEATURE = """\
Feature: A feature file in a directory named features

  Scenario: A flag resolves
    Given a stable provider
    Given a String-flag with key "string-flag" and a default value "bye"
    When the flag was evaluated with details
    Then the resolved details value should be "hi"
"""

_RESERVED_SUITE = '''\
"""An adoption that hands scenarios() a directory of its own named features."""

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
        name="reserved",
        control=control,
        new_provider=control.new_provider,
        capabilities={Capability.EVENTS},
    )


scenarios(str(pathlib.Path(__file__).parent / "features"))
'''


# -- reading a run back ------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Case:
    """One scenario as the stream reports it."""

    uri: str
    name: str
    row: tuple[tuple[str, str], ...]
    status: str

    @property
    def identity(self) -> tuple[str, str, tuple[tuple[str, str], ...]]:
        return (self.uri, self.name, self.row)


_SEVERITY = [
    "UNKNOWN",
    "PASSED",
    "SKIPPED",
    "PENDING",
    "UNDEFINED",
    "AMBIGUOUS",
    "FAILED",
]
"""Cucumber's own ordering: a test case is as bad as its worst step."""


@dataclasses.dataclass(frozen=True)
class Report:
    """One suite's pair of documents, read the way a consumer reads them."""

    envelope: dict[str, typing.Any]
    sources: dict[str, str]
    cases: list[Case]

    @property
    def canonical(self) -> list[Case]:
        return [case for case in self.cases if is_canonical_uri(case.uri)]

    @property
    def extensions(self) -> list[Case]:
        return [case for case in self.cases if not is_canonical_uri(case.uri)]

    def named(self, name: str) -> list[Case]:
        return [case for case in self.cases if case.name == name]

    @property
    def identities(self) -> set[tuple[str, str, tuple[tuple[str, str], ...]]]:
        return {case.identity for case in self.cases}


@dataclasses.dataclass(frozen=True)
class Run:
    """One subprocess run of a generated adoption."""

    directory: Path
    reports: Path
    result: subprocess.CompletedProcess[str]

    def report(self, name: str) -> Report:
        path = self.reports / f"{name}.json"
        assert path.exists(), (
            f"no report at {path}; pytest exited {self.result.returncode}\n"
            f"{self.result.stdout}\n{self.result.stderr}"
        )
        envelope = json.loads(path.read_text(encoding="utf-8"))
        return _read(envelope, self.reports / envelope["results"]["location"])


def _read(envelope: dict[str, typing.Any], stream_path: Path) -> Report:
    """Assemble a stream into scenarios by following the protocol's own links."""
    sources: dict[str, str] = {}
    names: dict[str, str] = {}
    rows: dict[str, tuple[tuple[str, str], ...]] = {}
    pickles: dict[str, dict[str, typing.Any]] = {}
    test_cases: dict[str, dict[str, typing.Any]] = {}
    started: dict[str, str] = {}
    results: dict[str, list[str]] = collections.defaultdict(list)

    for line in stream_path.read_text(encoding="utf-8").splitlines():
        message = json.loads(line)
        kind = next(iter(message))
        body = message[kind]
        if kind == "source":
            sources[body["uri"]] = body["data"]
        elif kind == "gherkinDocument":
            _index_document(body, names, rows)
        elif kind == "pickle":
            pickles[body["id"]] = body
        elif kind == "testCase":
            test_cases[body["id"]] = body
        elif kind == "testCaseStarted":
            started[body["id"]] = body["testCaseId"]
        elif kind == "testStepFinished":
            results[body["testCaseStartedId"]].append(body["testStepResult"]["status"])

    cases = []
    for started_id, case_id in started.items():
        pickle = pickles[test_cases[case_id]["pickleId"]]
        ast = pickle["astNodeIds"]
        cases.append(
            Case(
                uri=pickle["uri"],
                name=names[ast[0]],
                row=rows.get(ast[1], ()) if len(ast) > 1 else (),
                status=max(results[started_id], key=_SEVERITY.index),
            )
        )
    return Report(envelope=envelope, sources=sources, cases=cases)


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


def _pytest(directory: Path, reports: Path) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment[REPORT_DIR_ENV] = str(reports)
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(directory),
        ],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def _suite(name: str, call: str = _EXTENSION_CALL) -> str:
    return _SUITE_MODULE.format(name=name, call=call)


def _run(
    tmp_path_factory: pytest.TempPathFactory,
    modules: dict[str, str],
    features: dict[str, str] | None = None,
) -> Run:
    """Write an adoption, run it, and hand back what it wrote.

    Both mappings are keyed by a path relative to the adoption directory, so a
    fixture can put a module or a feature file wherever the property under test
    needs it -- including inside a directory named ``features``, which is the
    case that has to be refused.
    """
    directory = tmp_path_factory.mktemp("adoption")
    for relative, body in {**modules, **(features or {})}.items():
        path = directory / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    reports = tmp_path_factory.mktemp("reports")
    return Run(directory=directory, reports=reports, result=_pytest(directory, reports))


@pytest.fixture(scope="module")
def adoption(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """One session running three adoptions of the same provider.

    ``before`` is the call an adopter writes today, ``scenarios(features_path())``,
    which sees no extension however many are lying beside it. ``after`` is
    ``scenarios(*feature_paths())`` with an ordinary extension beside it.
    ``shadowed`` is the same again, in a directory of its own, with an extension
    that is a verbatim copy of a canonical feature file placed under a directory
    named ``features`` -- so that both routes to a canonical identity, the file's
    own name and its parent's, are taken at once.

    One session rather than three, because a subprocess pytest run is by far the
    most expensive thing in this file and the three suites are independent: each
    resolves its own ``TckConfig`` and writes its own pair of documents.
    """
    canonical = (Path(features_path()) / CANONICAL_FEATURE).read_text(encoding="utf-8")
    return _run(
        tmp_path_factory,
        {
            "test_before.py": _suite("before", _CANONICAL_CALL),
            "test_after.py": _suite("after", _EXTENSION_CALL),
            "conftest.py": _CONFTEST_MODULE,
            "shadow/test_shadow.py": _suite("shadowed"),
        },
        {
            f"{EXTENSIONS_DIRECTORY}/vendor.feature": _VENDOR_FEATURE,
            f"shadow/{EXTENSIONS_DIRECTORY}/features/{CANONICAL_FEATURE}": canonical,
        },
    )


# -- an extension is reported by the suite it ran in -------------------------


def test_an_extension_scenario_is_in_the_same_suites_report(adoption: Run) -> None:
    """One suite, one report, both sets of scenarios in it.

    The report is written per ``TckConfig``, so an extension scenario appearing
    in the same report as the canonical ones is not a presentational detail: it
    is the same suite, which is the same provider registration and the same
    backend control.
    """
    assert adoption.result.returncode == 0, adoption.result.stdout
    report = adoption.report("after")

    vendor = report.named(VENDOR_SCENARIO)
    assert len(vendor) == 1, report.extensions
    assert vendor[0].status == "PASSED"
    assert vendor[0].uri == VENDOR_URI

    assert report.canonical, "the canonical scenarios must have run too"
    assert {case.status for case in report.canonical} <= {"PASSED", "SKIPPED", "FAILED"}


def test_the_extension_feature_is_reported_under_its_own_prefix(
    adoption: Run,
) -> None:
    """Which is what keeps an adopter's claim apart from the specification's.

    ``extensions/`` is the prefix the Go and JavaScript suites mount extensions
    under too, so a consumer holding reports from several languages applies one
    rule.
    """
    report = adoption.report("after")
    assert [case.uri for case in report.extensions] == [VENDOR_URI]
    assert report.sources[VENDOR_URI] == _VENDOR_FEATURE
    assert all(case.uri.startswith("features/") for case in report.canonical)


def test_the_envelope_is_unaffected_by_an_extension(adoption: Run) -> None:
    """The report schema has no slot for extensions and needs none.

    Everything an extension adds is a scenario in the results payload, where a
    uri already distinguishes it. An envelope field would be a second place for
    the same fact to live.
    """
    envelope = adoption.report("after").envelope
    assert envelope["provider"]["configuration"] == "after"
    assert set(envelope) == {
        "schemaVersion",
        "provider",
        "sdk",
        "tck",
        "backend",
        "declaration",
        "results",
    }


# -- and changes nothing for an adopter who has none -------------------------


def test_the_canonical_scenarios_are_the_ones_that_always_ran(
    adoption: Run,
) -> None:
    """An extension adds; it does not alter.

    ``before`` is the call an adopter writes today and sees no extension. Every
    scenario it ran, ``after`` ran too -- same rows, same outcomes, same sources
    -- and the only difference between the two is what the extension added. An
    adopter who has no extensions is the same comparison with the right-hand side
    empty, which is what ``feature_paths()`` returning the canonical path alone
    makes true by construction rather than by luck.
    """
    assert adoption.result.returncode == 0, adoption.result.stdout
    before = adoption.report("before")
    after = adoption.report("after")

    assert not before.extensions, "features_path() must see no extension"
    assert {case.identity: case.status for case in after.canonical} == {
        case.identity: case.status for case in before.cases
    }
    assert after.identities - before.identities == {(VENDOR_URI, VENDOR_SCENARIO, ())}
    assert {
        uri: source for uri, source in after.sources.items() if is_canonical_uri(uri)
    } == before.sources


def test_an_extension_does_not_change_the_envelope_a_suite_writes(
    adoption: Run,
) -> None:
    """Everything but the two fields that necessarily differ.

    ``results`` names a file and digests its bytes, and the bytes carry
    timestamps; ``configuration`` is the suite name, which is what tells the two
    generated suites apart in the first place.
    """
    before = dict(adoption.report("before").envelope)
    after = dict(adoption.report("after").envelope)
    for envelope in (before, after):
        del envelope["results"]
        envelope["provider"] = {
            key: value
            for key, value in envelope["provider"].items()
            if key != "configuration"
        }
    assert after == before


# -- and cannot stand in for a canonical scenario ----------------------------


def test_an_extension_cannot_replace_a_canonical_feature_file(
    adoption: Run,
) -> None:
    """The hazard Java measured, checked at the point it would have bitten.

    A verbatim copy of ``errors.feature`` under ``tck-extensions/features/``
    reaches pytest-bdd as ``features/errors.feature`` -- the canonical uri. The
    uri the payload reports is derived from where the file is instead, so the
    canonical source is still the packaged one, the copy is reported as an
    extension, and both ran.
    """
    report = adoption.report("shadowed")
    canonical_uri = f"features/{CANONICAL_FEATURE}"
    extension_uri = f"extensions/features/{CANONICAL_FEATURE}"

    packaged = (Path(features_path()) / CANONICAL_FEATURE).read_text(encoding="utf-8")
    assert report.sources[canonical_uri] == packaged
    assert report.sources[extension_uri] == packaged

    # Both files ran: the copy neither replaced the canonical one nor was
    # silently dropped for colliding with it.
    canonical = {
        case.identity for case in report.canonical if case.uri == canonical_uri
    }
    copied = {case.identity for case in report.cases if case.uri == extension_uri}
    assert canonical, "the canonical feature file did not run"
    assert len(copied) == len(canonical)
    assert not any(is_canonical_uri(case.uri) for case in report.extensions)


def test_a_shadowing_extension_does_not_disturb_the_canonical_run(
    adoption: Run,
) -> None:
    """The canonical scenarios are the same ones, with the same outcomes.

    Compared against a run that has no extension at all rather than against a
    number written down here, so a change to the canonical assets cannot leave
    this passing while the copy quietly displaces something.
    """
    shadow = adoption.report("shadowed")
    baseline = adoption.report("before")
    assert {case.identity: case.status for case in shadow.canonical} == {
        case.identity: case.status for case in baseline.cases
    }


def test_a_directory_named_features_is_refused(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """The one collision the naming convention cannot rule out on its own.

    An adopter can still hand ``scenarios()`` a directory of their own named
    ``features``, and its files are then named exactly as canonical ones would
    be. No report is written for that suite: a document presenting an adopter's
    feature file as the specification's is worse than no document, because it is
    the one thing a consumer cannot check.
    """
    run = _run(
        tmp_path_factory,
        {"test_reserved.py": _RESERVED_SUITE},
        {"features/local.feature": _RESERVED_FEATURE},
    )
    assert run.result.returncode != 0, run.result.stdout
    assert "features/local.feature is not a canonical feature file" in run.result.stdout
    assert EXTENSIONS_DIRECTORY in run.result.stdout, "the message must say the fix"
    assert not list(run.reports.glob("*.json")), "no report may be written"


def test_two_extension_files_cannot_share_one_uri(
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Deriving the uri from the location narrows the collision; it does not end it.

    A ``tck-extensions`` directory nested inside another one reaches the same
    uri as its namesake at the root, and so would two test modules sharing one
    ``tck_config``. A Messages stream carries one source per uri, so the second
    file's scenarios would be reported against the first file's pickles wherever
    the names matched -- which here they do, deliberately. Refused rather than
    resolved.
    """
    nested = f"{EXTENSIONS_DIRECTORY}/nested/{EXTENSIONS_DIRECTORY}/vendor.feature"
    run = _run(
        tmp_path_factory,
        {"test_collide.py": _suite("collide"), "conftest.py": _CONFTEST_MODULE},
        {
            f"{EXTENSIONS_DIRECTORY}/vendor.feature": _VENDOR_FEATURE,
            nested: _NESTED_FEATURE,
        },
    )
    assert run.result.returncode != 0, run.result.stdout
    assert f"{VENDOR_URI} is the uri of 2 different feature files" in run.result.stdout
    assert not list(run.reports.glob("*.json")), "no report may be written"
