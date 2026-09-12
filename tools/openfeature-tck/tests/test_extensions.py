"""What an adopter's own scenarios may and may not do.

An adopter with provider-specific behaviour -- flagd's ``fractional`` targeting, a
proprietary rollout rule -- has to be able to pin it in the same run as the
contract it sits on top of, or they end up maintaining a second harness beside
the one the TCK gives them. So the properties checked here are the ones that make
that safe rather than merely possible:

* an extension scenario runs **inside** the canonical suite -- same session, same
  provider registration, same backend control -- with a step definition the
  adopter wrote in their own ``conftest.py`` and nothing else registered;
* an adoption without extensions runs exactly what it ran before, scenario for
  scenario and outcome for outcome;
* a feature file's identity comes from where the file is, so an extension cannot
  take a canonical scenario's.

The last is not hypothetical. Java's suite discovered a same-named feature file
in a second classpath root silently *replacing* the canonical one, and the run
went green having asked the adopter's questions instead of the specification's.
The Python route to the same place is narrower and just as quiet: pytest-bdd
names a feature file by its parent directory joined to its own name, so a file at
``extensions/gherkin/errors.feature`` arrives under the uri the canonical
``errors.feature`` already occupies.

The first three are properties of how a whole session runs rather than of what a
function returns, so they are checked against real pytest sessions in
subprocesses, read back through pytest's own JUnit XML. Reading them back from a
conformance report would be circular here and impossible anyway: this package
writes none.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import (
    EXTENSIONS_DIRECTORY,
    feature_paths,
    features_path,
)
from openfeature.contrib.tools.tck.extensions import (
    CANONICAL_DIRECTORY,
    EXTENSIONS_URI_PREFIX,
    collision_problem,
    extension_root,
    is_canonical,
    is_canonical_uri,
    reserved_prefix_problem,
    uri_collisions,
    uri_for,
)

CANONICAL_FEATURE = "errors.feature"
"""The canonical file the collision cases are written against, chosen because it
is the one whose scenarios an extension could most plausibly want to restate."""

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
# It asks the TCK's own per-scenario state what happened, which is what makes
# "the same session and the same provider" checkable rather than asserted: a
# second harness would have a second provider, or none, and none of the canonical
# steps would have run.
_CONFTEST_MODULE = """\
import pytest
from pytest_bdd import then

from openfeature.contrib.tools.tck import TckState

DEVIATION = "[boolean-flag-Integer-1]"


@then("the vendor rule ran against the provider the suite registered")
def vendor_rule_ran(tck_state: TckState) -> None:
    assert tck_state.client is not None, "no provider was registered"
    assert tck_state.last is not None, "the canonical steps did not run here"
    assert tck_state.last.value == "hi", tck_state.last


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


# -- reading a run back ------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Run:
    """One subprocess run of a generated adoption."""

    directory: Path
    result: subprocess.CompletedProcess[str]
    outcomes: dict[str, str]


def _outcomes(report: Path) -> dict[str, str]:
    """Read a JUnit XML report into ``node id -> passed | failed | skipped``.

    pytest's own results format, because the question is what the session did
    and pytest is the thing that knows. It records one ``testcase`` per test with
    the file it came from, which is what lets two suites in one directory be
    told apart.
    """
    outcomes: dict[str, str] = {}
    # Not untrusted input: the file is one pytest wrote seconds ago, in a
    # temporary directory this test made, from a subprocess this test started.
    root = ElementTree.parse(report).getroot()  # noqa: S314
    for case in root.iter("testcase"):
        statuses = {
            "failure": "failed",
            "error": "failed",
            "skipped": "skipped",
        }
        status = "passed"
        for tag, named in statuses.items():
            if case.find(tag) is not None:
                status = named
                break
        node = f"{case.get('classname', '')}::{case.get('name', '')}"
        outcomes[node] = status
    return outcomes


def _run(
    tmp_path_factory: pytest.TempPathFactory,
    modules: dict[str, str],
    features: dict[str, str] | None = None,
) -> Run:
    """Write an adoption, run it in a subprocess, and read the results back.

    Both mappings are keyed by a path relative to the adoption directory, so a
    case can put a module or a feature file wherever the property under test
    needs it.
    """
    directory = tmp_path_factory.mktemp("adoption")
    for relative, body in {**modules, **(features or {})}.items():
        path = directory / Path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    report = directory / "results.xml"
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--junitxml={report}",
            str(directory),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    outcomes = _outcomes(report) if report.exists() else {}
    return Run(directory=directory, result=result, outcomes=outcomes)


def _suite(name: str, call: str = _EXTENSION_CALL) -> str:
    return _SUITE_MODULE.format(name=name, call=call)


@pytest.fixture(scope="module")
def adoption(tmp_path_factory: pytest.TempPathFactory) -> Run:
    """One session running two adoptions of the same provider.

    ``before`` is the call an adopter wrote before any of this,
    ``scenarios(features_path())``, which sees no extension however many are
    lying beside it. ``after`` is ``scenarios(*feature_paths())`` with an
    ordinary extension beside it. Having both in one run is what lets "an
    extension adds and does not alter" be a comparison rather than a number
    written down here.

    One session rather than two, because a subprocess pytest run is by far the
    most expensive thing in this file and the two suites are independent: each
    resolves its own ``TckConfig`` under its own OpenFeature domain.
    """
    return _run(
        tmp_path_factory,
        {
            "test_before.py": _suite("before", _CANONICAL_CALL),
            "test_after.py": _suite("after", _EXTENSION_CALL),
            "conftest.py": _CONFTEST_MODULE,
        },
        {f"{EXTENSIONS_DIRECTORY}/vendor.feature": _VENDOR_FEATURE},
    )


def _of(run: Run, module: str) -> dict[str, str]:
    """The outcomes belonging to one of the generated suites, keyed by test name.

    JUnit XML names the module in dotted form, so the two generated suites in one
    directory are told apart by the last segment of it.
    """
    return {
        node.split("::", 1)[1]: status
        for node, status in run.outcomes.items()
        if node.split("::", 1)[0].rsplit(".", 1)[-1] == module
    }


def _contributed(run: Run) -> dict[str, str]:
    """What the extension added: the tests ``after`` ran and ``before`` did not.

    Identified by difference rather than by name. pytest-bdd derives a test
    function's name from the scenario name by a munging of its own -- an
    apostrophe disappears where a space becomes an underscore -- and reproducing
    that here would pin pytest-bdd's spelling rather than this package's
    behaviour.
    """
    before = _of(run, "test_before")
    return {
        name: status
        for name, status in _of(run, "test_after").items()
        if name not in before
    }


# -- an extension runs inside the canonical suite ----------------------------


def test_an_extension_scenario_runs_in_the_canonical_suite(adoption: Run) -> None:
    """One suite, one session, both sets of scenarios in it.

    The extension scenario passes only if it reached the provider the suite
    registered and the canonical steps ran in it, because that is what its own
    step asserts -- so this is not a presentational fact about collection. It is
    the same suite, which is the same provider registration and the same backend
    control.
    """
    assert adoption.result.returncode == 0, adoption.result.stdout

    contributed = _contributed(adoption)
    assert len(contributed) == 1, adoption.outcomes
    [(name, status)] = contributed.items()
    assert "vendor_rule" in name, name
    assert status == "passed"

    canonical = _of(adoption, "test_after")
    assert len(canonical) > 1, "the canonical scenarios must have run too"
    assert "passed" in canonical.values()


def test_the_extension_step_came_from_the_adopters_conftest(adoption: Run) -> None:
    """Nothing was registered, imported or configured to make that step resolve.

    pytest collects ``conftest.py`` on its own and pytest-bdd resolves steps
    through the fixture system, so a step defined beside the test module is in
    scope for the scenarios generated into it. An unresolved step is a *failure*
    rather than an omission, which is why asserting that the scenario passed is
    enough to pin this.
    """
    conftest = (adoption.directory / "conftest.py").read_text(encoding="utf-8")
    assert "the vendor rule ran against the provider the suite registered" in conftest
    assert set(_contributed(adoption).values()) == {"passed"}


# -- and changes nothing for an adopter who has none -------------------------


def test_an_extension_adds_scenarios_and_alters_none(adoption: Run) -> None:
    """``before`` is what an adopter ran before extensions existed.

    Every test it generated, ``after`` generated too, with the same outcome, and
    the only difference between the two is the one scenario the extension added.
    An adopter who has no extensions is the same comparison with the right-hand
    side empty, which is what ``feature_paths()`` returning the canonical path
    alone makes true by construction rather than by luck.
    """
    before = _of(adoption, "test_before")
    after = _of(adoption, "test_after")
    assert before, "the baseline suite generated nothing"

    assert len(_contributed(adoption)) == 1
    assert {name: after[name] for name in before} == before


def test_features_path_sees_no_extension_however_many_are_beside_it(
    adoption: Run,
) -> None:
    """The older call still means exactly what it meant: the canonical set.

    Both generated suites sit in the same directory as the ``extensions``
    directory, so the one that asks for ``features_path()`` is asking with an
    extension in arm's reach and must still not see it.
    """
    assert (adoption.directory / EXTENSIONS_DIRECTORY).is_dir()
    assert set(_of(adoption, "test_before")) < set(_of(adoption, "test_after"))


# -- finding an adopter's feature files --------------------------------------


def test_feature_paths_is_the_canonical_set_when_there_is_no_extension_directory() -> (
    None
):
    """This test module has no ``extensions`` beside it, and gets one path."""
    assert not (Path(__file__).parent / EXTENSIONS_DIRECTORY).exists()
    assert feature_paths() == (features_path(),)


def test_an_extension_directory_counts_only_when_it_is_a_directory(
    tmp_path: Path,
) -> None:
    """``None`` rather than a path that contributes nothing.

    So that an adopter without extensions hands ``scenarios()`` exactly what
    they handed it before -- and so that a *file* of that name, which pytest-bdd
    would choke on, is not offered as a feature directory.
    """
    assert extension_root(tmp_path) is None

    (tmp_path / EXTENSIONS_DIRECTORY).write_text("not a directory", encoding="utf-8")
    assert extension_root(tmp_path) is None

    (tmp_path / EXTENSIONS_DIRECTORY).unlink()
    (tmp_path / EXTENSIONS_DIRECTORY).mkdir()
    assert extension_root(tmp_path) == tmp_path / EXTENSIONS_DIRECTORY


def test_the_canonical_features_are_found_inside_the_distribution() -> None:
    """No submodule and no directory layout of the adopter's own."""
    packaged = Path(features_path())
    assert (packaged / CANONICAL_FEATURE).is_file()
    assert is_canonical(packaged / CANONICAL_FEATURE)
    assert not is_canonical(Path(__file__))


# -- deriving the uri --------------------------------------------------------


def test_the_two_prefixes_are_the_ones_appendix_f_names() -> None:
    """Pinned as literals, because every other assertion here uses the constants.

    Those assertions hold whatever the constants say, so renaming one would leave
    the suite green while the uris it emits stopped joining with another
    language's -- which is the failure that happened. Appendix F fixes both
    strings: a canonical feature is identified by its path relative to the
    specification's asset directory, and ``gherkin`` is the directory it occupies
    there; an extension mounts under ``extensions``.
    """
    assert CANONICAL_DIRECTORY == "gherkin"
    assert EXTENSIONS_URI_PREFIX == "extensions"
    assert CANONICAL_DIRECTORY != EXTENSIONS_DIRECTORY, (
        "an extensions directory sharing the canonical name is how an extension "
        "comes to occupy a canonical file's identity"
    )


def test_the_canonical_assets_keep_the_reserved_prefix() -> None:
    canonical = Path(features_path()) / CANONICAL_FEATURE
    assert uri_for(canonical) == f"{CANONICAL_DIRECTORY}/{CANONICAL_FEATURE}"
    assert is_canonical_uri(f"{CANONICAL_DIRECTORY}/{CANONICAL_FEATURE}")
    assert (
        reserved_prefix_problem(f"{CANONICAL_DIRECTORY}/{CANONICAL_FEATURE}", canonical)
        is None
    )


def test_an_extension_keeps_its_layout_below_the_extensions_prefix(
    tmp_path: Path,
) -> None:
    """Whatever the adopter's own directory layout under the root looks like.

    Including one that reproduces the canonical name, which is the collision the
    derivation exists for: pytest-bdd would have called the second of these
    ``gherkin/errors.feature``.
    """
    root = tmp_path / EXTENSIONS_DIRECTORY
    assert uri_for(root / "vendor.feature") == "extensions/vendor.feature"
    assert (
        uri_for(root / CANONICAL_DIRECTORY / CANONICAL_FEATURE)
        == f"{EXTENSIONS_URI_PREFIX}/{CANONICAL_DIRECTORY}/{CANONICAL_FEATURE}"
    )
    assert (
        uri_for(root / "a" / "b" / "vendor.feature") == "extensions/a/b/vendor.feature"
    )
    assert not is_canonical_uri(
        f"{EXTENSIONS_URI_PREFIX}/{CANONICAL_DIRECTORY}/{CANONICAL_FEATURE}"
    )


def test_a_derived_uri_is_slash_separated_on_every_platform(tmp_path: Path) -> None:
    """A uri identifies a feature file, so it cannot depend on where it ran.

    The paths these are built from are ``pathlib`` paths, which are
    backslash-separated on Windows. A run there has to be comparable with one on
    Linux, and it is not if the same file is identified two ways.
    """
    nested = tmp_path / EXTENSIONS_DIRECTORY / "a" / "b" / "vendor.feature"
    derived = uri_for(nested)
    assert derived == "extensions/a/b/vendor.feature"
    assert derived is not None and "\\" not in derived


def test_a_file_that_is_neither_is_left_to_pytest_bdd(tmp_path: Path) -> None:
    """``None`` rather than a guess: the caller falls back to what the runner said."""
    assert uri_for(tmp_path / "loose.feature") is None


def test_a_local_file_under_the_reserved_prefix_is_a_problem(tmp_path: Path) -> None:
    """The one route to a canonical-looking uri the convention cannot close.

    An adopter may still hand ``scenarios()`` a directory of their own named
    ``gherkin``, and its files are then named exactly as canonical ones would
    be. Reported rather than raised: the scenarios are the adopter's to run, and
    it is publishing them as the specification's that has to be refused.
    """
    local = tmp_path / CANONICAL_DIRECTORY / "local.feature"
    problem = reserved_prefix_problem(f"{CANONICAL_DIRECTORY}/local.feature", local)
    assert problem is not None
    assert EXTENSIONS_DIRECTORY in problem, "the message must say the fix"
    assert str(local) in problem


def test_two_files_that_would_share_one_uri_are_reported(tmp_path: Path) -> None:
    """Deriving the uri from the location narrows the collision; it does not end it.

    An ``extensions`` directory nested inside another one reaches the same uri
    as its namesake at the root, and so would two test modules sharing one
    ``tck_config``.
    """
    root = tmp_path / EXTENSIONS_DIRECTORY
    nested = root / "nested" / EXTENSIONS_DIRECTORY / "vendor.feature"
    collisions = uri_collisions(
        [
            ("extensions/vendor.feature", root / "vendor.feature"),
            ("extensions/vendor.feature", nested),
        ]
    )
    assert set(collisions) == {"extensions/vendor.feature"}

    problem = collision_problem(
        "extensions/vendor.feature", collisions["extensions/vendor.feature"]
    )
    assert "2 different feature files" in problem
    assert EXTENSIONS_DIRECTORY in problem


def test_distinct_extension_paths_do_not_collide(tmp_path: Path) -> None:
    """The layouts that are fine, including the one that only looks like a clash."""
    root = tmp_path / EXTENSIONS_DIRECTORY
    assert not uri_collisions(
        [
            ("extensions/vendor.feature", root / "vendor.feature"),
            ("extensions/a/vendor.feature", root / "a" / "vendor.feature"),
            # One file reached by two routes is one file, not a collision.
            ("extensions/vendor.feature", root / "a" / ".." / "vendor.feature"),
        ]
    )
