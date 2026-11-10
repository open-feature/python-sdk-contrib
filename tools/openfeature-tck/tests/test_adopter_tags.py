"""Which of an adopter's own scenarios a run asks, and which it skips.

An adoption whose extensions cover more than the provider does at the moment --
two backend modes, a rule behind a version it has not deployed -- needs to be
able to say so in configuration rather than by deleting feature files or
maintaining a branch per mode. ``include_tags`` and ``exclude_tags`` are that
statement, and the properties worth pinning are the ones that decide what the
statement *means*:

* an **untagged** extension scenario is skipped while ``include_tags`` is set,
  which is what makes it a filter rather than a hint. It is the only case the two
  readings disagree about, so it is the one that has to be checked against a real
  session rather than asserted here;
* **canonical scenarios are exempt**: the specification's scenarios are not an
  adopter's to select, and a selection that reached them would be a conformance
  suite configured to skip conformance;
* **exclude wins over include**, so the narrower statement is not overridden by
  the broader one;
* a **capability tag** is refused in either option, so this gate can never skip
  what a declaration already gates -- and so cannot contradict one;
* every skip **names the tag** that caused it, because a selection whose effect
  is an absent scenario is indistinguishable from one that was satisfied.

The first three are properties of a session rather than of a function, so they
are read back from a real pytest run in a subprocess, through pytest's own JUnit
XML -- the same route :mod:`test_extensions` takes, and for the same reason: what
is being asked is what the session did, and pytest is the thing that knows.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
import types
import typing
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import pytest

from openfeature.contrib.tools.tck import (
    EXTENSIONS_DIRECTORY,
    Capability,
    InProcessControl,
    TckConfig,
    plugin,
)
from openfeature.contrib.tools.tck import capability as capability_module
from openfeature.contrib.tools.tck import config as config_module

INCLUDED = "@mode-a"
"""The tag the generated adoption selects on."""

EXCLUDED = "@old-version"
"""The tag it holds back, carried by a scenario that also carries ``INCLUDED``,
so the run says which of the two options won."""


def _config(**overrides: typing.Any) -> TckConfig:
    """A configuration that is valid and selects nothing in particular."""
    settings: dict[str, typing.Any] = {
        "name": "stub",
        "control": InProcessControl(),
        "new_provider": lambda: None,
        "capabilities": frozenset(),
    }
    settings.update(overrides)
    return TckConfig(**settings)


# -- the selection, against a real session -----------------------------------


_SUITE_MODULE = '''\
"""An adoption selecting its own extension scenarios, generated for this test."""

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
        name="selective",
        control=control,
        new_provider=control.new_provider,
        capabilities={{Capability.EVENTS, Capability.OBJECT}},
        include_tags=("{included}",),
        exclude_tags=("{excluded}",),
    )


scenarios(*feature_paths())
'''

# The suite's own deviation, so the generated run's exit code says something
# about the selection rather than about python-sdk#619.
_CONFTEST_MODULE = """\
import pytest

DEVIATION = "[boolean-flag-Integer-1]"


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name.endswith(DEVIATION):
            item.add_marker(pytest.mark.xfail(reason="python-sdk#619"))
"""

# Every combination the rule distinguishes, including the untagged scenario the
# two readings of `include_tags` disagree about.
_EXTENSION_FEATURE = f"""Feature: An adopter selects its own extension scenarios by tag

  {INCLUDED}
  Scenario: An extension scenario carrying the included tag
    Given a stable provider

  {INCLUDED} {EXCLUDED}
  Scenario: An extension scenario carrying an excluded tag as well
    Given a stable provider

  @mode-b
  Scenario: An extension scenario tagged for the other mode only
    Given a stable provider

  Scenario: An extension scenario with no tags at all
    Given a stable provider

  @mode-b @targeting
  Scenario: An extension scenario gated by the selection and by a capability
    Given a stable provider
"""


@dataclasses.dataclass(frozen=True)
class Outcome:
    """What a session did with one scenario, and what it said about it."""

    status: str
    message: str


def _outcomes(report: Path) -> dict[str, Outcome]:
    """Read a JUnit XML report into ``test name -> outcome``.

    The message matters as much as the status here: a skip whose reason does not
    name the tag that caused it leaves an adopter with several options
    configured and no way to tell which one matched.
    """
    outcomes: dict[str, Outcome] = {}
    # Not untrusted input: the file is one pytest wrote seconds ago, in a
    # temporary directory this test made, from a subprocess this test started.
    root = ElementTree.parse(report).getroot()  # noqa: S314
    for case in root.iter("testcase"):
        status = "passed"
        message = ""
        for tag, named in (
            ("failure", "failed"),
            ("error", "failed"),
            ("skipped", "skipped"),
        ):
            found = case.find(tag)
            if found is not None:
                status = named
                message = found.get("message", "")
                break
        name = case.get("name", "")
        outcomes[name] = Outcome(status=status, message=message)
    return outcomes


@pytest.fixture(scope="module")
def selective_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Outcome]:
    """One session of an adoption that includes one tag and excludes another."""
    directory = tmp_path_factory.mktemp("selective")
    files = {
        "test_selective.py": _SUITE_MODULE.format(included=INCLUDED, excluded=EXCLUDED),
        "conftest.py": _CONFTEST_MODULE,
        f"{EXTENSIONS_DIRECTORY}/selection.feature": _EXTENSION_FEATURE,
    }
    for relative, body in files.items():
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
    assert report.exists(), result.stdout + result.stderr
    outcomes = _outcomes(report)
    assert outcomes, result.stdout + result.stderr
    return outcomes


def _extension(outcomes: dict[str, Outcome], fragment: str) -> Outcome:
    """The one extension scenario whose test name contains ``fragment``.

    By fragment rather than by name, because pytest-bdd munges a scenario name
    into a function name by a convention of its own, and reproducing it here
    would pin pytest-bdd's spelling rather than this package's behaviour.
    """
    matched = {name: o for name, o in outcomes.items() if fragment in name}
    assert len(matched) == 1, f"{fragment}: {sorted(outcomes)}"
    return next(iter(matched.values()))


def test_an_untagged_extension_scenario_is_skipped_under_an_include(
    selective_run: dict[str, Outcome],
) -> None:
    """The case the two readings of ``include_tags`` disagree about.

    Read as a hint it would run, having said nothing about any mode; read as a
    filter it does not, because it does not say it is about the mode being run.
    It is a filter -- so a scenario an adopter forgot to tag is skipped in every
    mode's run, saying so, rather than running in all of them.
    """
    untagged = _extension(selective_run, "no_tags_at_all")

    assert untagged.status == "skipped", untagged
    assert "none of the tags this adoption includes" in untagged.message
    assert INCLUDED in untagged.message


def test_the_selection_runs_the_scenarios_it_names(
    selective_run: dict[str, Outcome],
) -> None:
    """The ordinary half: an included tag and no excluded one runs.

    Beside the skips rather than taken for granted, because a gate that skipped
    everything would satisfy every other case in this file.
    """
    included = _extension(selective_run, "carrying_the_included_tag")
    assert included.status == "passed", included

    other_mode = _extension(selective_run, "other_mode_only")
    assert other_mode.status == "skipped", other_mode
    assert "none of the tags this adoption includes" in other_mode.message


def test_an_excluded_tag_wins_over_an_included_one(
    selective_run: dict[str, Outcome],
) -> None:
    """Both tags on one scenario, and the narrower statement is the one that holds.

    The skip names the excluded tag, so the run says which of the two options
    decided it -- an adoption with several exclusions otherwise has to guess.
    """
    both = _extension(selective_run, "excluded_tag_as_well")

    assert both.status == "skipped", both
    assert f"carries {EXCLUDED}" in both.message
    assert "excludes" in both.message


def test_a_canonical_scenario_is_never_skipped_by_this_gate(
    selective_run: dict[str, Outcome],
) -> None:
    """The specification's scenarios are not an adopter's to select.

    Checked over the whole session rather than over one scenario: canonical
    scenarios carry no adopter tag at all, so under an include every one of them
    would be skipped if the exemption were missing -- which would be a
    conformance suite configured to skip conformance, reported as a clean run.

    The capability skips the narrowed declaration produces are left alone; what
    may not appear in a canonical scenario's reason is this gate's wording.
    """
    canonical = {
        name: outcome
        for name, outcome in selective_run.items()
        if "extension_scenario" not in name
    }
    assert canonical, sorted(selective_run)
    assert any(outcome.status == "passed" for outcome in canonical.values()), canonical

    for name, outcome in canonical.items():
        assert "this adoption includes" not in outcome.message, name
        assert "this adoption excludes" not in outcome.message, name


def test_a_deselected_scenario_is_not_reported_as_a_withheld_capability(
    selective_run: dict[str, Outcome],
) -> None:
    """``@mode-b @targeting``, deselected and undeclared, reports the selection.

    The gate order, measured where it is visible: a report saying this provider
    does not declare ``@targeting`` would be describing a question the suite
    never put, because the scenario asking it was deselected first.
    """
    doubly = _extension(selective_run, "selection_and_by_a_capability")

    assert doubly.status == "skipped", doubly
    assert "none of the tags this adoption includes" in doubly.message
    assert "does not declare capability" not in doubly.message


def test_the_language_wide_reason_outranks_a_tag_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other side of the order, which no adoption's options may bury.

    ``INEXPRESSIBLE_CAPABILITIES`` is empty in Python, so this is the only place
    the tier can be exercised; patched on the module because the production code
    reads the mapping through the module global at call time.
    """
    monkeypatch.setattr(
        capability_module,
        "INEXPRESSIBLE_CAPABILITIES",
        types.MappingProxyType({Capability.LARGE_INTEGERS: "pretended, for one test"}),
    )
    scenario = types.SimpleNamespace(
        feature=types.SimpleNamespace(
            filename=str(Path("suite") / EXTENSIONS_DIRECTORY / "x.feature")
        )
    )
    node = types.SimpleNamespace(
        function=types.SimpleNamespace(__scenario__=scenario),
        iter_markers=lambda: iter(
            [
                types.SimpleNamespace(name=Capability.LARGE_INTEGERS.value),
                types.SimpleNamespace(name="mode-b"),
            ]
        ),
    )
    request = types.SimpleNamespace(
        node=node,
        getfixturevalue=lambda name: _config(exclude_tags=("@mode-b",)),
    )

    with pytest.raises(pytest.skip.Exception) as raised:
        plugin.apply_scenario_gates(typing.cast("pytest.FixtureRequest", request))

    message = str(raised.value)
    assert "cannot be expressed by this SDK" in message
    assert "this adoption excludes" not in message


# -- the skip reasons --------------------------------------------------------


def test_an_exclusion_names_the_tag_that_matched() -> None:
    """Not merely the option: one of several exclusions is what held it back."""
    config = _config(exclude_tags=("@old-version", "@slow"))

    reason = plugin.excluded_skip_reason({"@mode-a", "@old-version"}, config)
    assert reason is not None
    assert "carries @old-version" in reason
    assert "@slow" not in reason.split("Excluded:")[0]
    # And the whole selection is quoted after it, so a reader sees what else
    # this adoption holds back.
    assert "Excluded: @old-version @slow" in reason

    assert plugin.excluded_skip_reason({"@mode-a"}, config) is None


def test_an_empty_include_set_selects_everything() -> None:
    """The default, and the behaviour every existing adoption keeps."""
    assert plugin.not_included_skip_reason(set(), _config()) is None
    assert plugin.not_included_skip_reason({"@anything"}, _config()) is None

    config = _config(include_tags=("@mode-a",))
    assert plugin.not_included_skip_reason({"@mode-a", "@other"}, config) is None
    assert plugin.not_included_skip_reason(set(), config) is not None


# -- what cannot be selected on ----------------------------------------------


@pytest.mark.parametrize("option", ["include_tags", "exclude_tags"])
def test_a_capability_tag_cannot_be_selected_on(option: str) -> None:
    """So this gate can never skip what a declaration already gates.

    A capability skip carries the declaration that produced it, which is what
    makes it an answer rather than a hole. Selecting on the same tag here would
    skip the same scenarios while recording nothing about why -- and an adoption
    could exclude a capability it declares, leaving the report claiming a
    capability no scenario was asked about.
    """
    # Written either way: the tag, and the enum member, which is a ``str`` whose
    # value carries no at-sign and would otherwise read as malformed.
    for written in (Capability.EVENTS.tag, Capability.EVENTS):
        with pytest.raises(ValueError, match="TCK capability tags @events") as raised:
            _config(**{option: (written,)})

        message = str(raised.value)
        assert option in message
        assert "capabilities" in message


def test_a_malformed_tag_is_refused_rather_than_matching_nothing() -> None:
    """A tag is the spelling a scenario carries, or it matches no scenario.

    Refused rather than dropped, because a selection that matches nothing reads
    in a report exactly like one that was satisfied.
    """
    for written in ("mode-a", "@", " @mode-a", "@mode-a "):
        with pytest.raises(ValueError, match="a tag is the Gherkin spelling"):
            _config(include_tags=(written,))

    # A bare string is the near miss worth its own message: a frozenset of one
    # is one character at a time.
    with pytest.raises(ValueError, match="single string"):
        _config(exclude_tags="@mode-a")


def test_one_tag_cannot_be_both_included_and_excluded() -> None:
    """It has no reading: exclude wins, so including it says nothing."""
    with pytest.raises(ValueError, match="named by both include_tags"):
        _config(include_tags=("@mode-a", "@mode-b"), exclude_tags=("@mode-a",))

    assert config_module.tag_selection_problems(("@mode-a",), ("@mode-b",)) == []


def test_a_tag_selection_is_normalised_however_it_was_written() -> None:
    """A list, a set or a generator all arrive as the same frozenset."""
    expected = frozenset({"@mode-a", "@mode-b"})

    def written() -> list[typing.Any]:
        # Rebuilt per option: normalising consumes the generator, which is the
        # point of normalising it.
        return [
            ["@mode-a", "@mode-b", "@mode-a"],
            {"@mode-a", "@mode-b"},
            (tag for tag in ("@mode-a", "@mode-b")),
        ]

    for tags in written():
        assert _config(include_tags=tags).include_tags == expected
    for tags in written():
        assert _config(exclude_tags=tags).exclude_tags == expected

    assert _config().include_tags == frozenset()
    assert _config().exclude_tags == frozenset()
