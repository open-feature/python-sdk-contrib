"""The machine-readable conformance report: what a run of the suite claims.

A run of the suite produces a pass or a fail on a terminal, which is enough for
the person who started it and useless to anyone else. The report is the same run
written down in a form something other than a human can read -- a comparison
page, an aggregator, a release gate -- against a schema owned by the
specification rather than by this package, so that four languages emit the same
document.

The load-bearing part is the per-scenario list. Appendix F requires that a
scenario skipped for an undeclared capability is reported as skipped *with the
reason* and never as passed, and a summary line cannot be checked against that
rule by anything downstream. Recording every scenario's outcome individually
makes the rule checkable by the consumer instead of dependent on each runner's
summary being trustworthy -- and the outcomes are required to be complete,
because a report that silently omitted what it skipped would satisfy the letter
of the rule while still misleading its reader.

See https://github.com/open-feature/spec/issues/424 for the format and
``specification/assets/provider-tck/report/`` for the schema.
"""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import json
import re
import typing
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .capability import Capability, capability_for_tag
from .config import TckConfig

__all__ = [
    "REPORT_DIR_ENV",
    "SCHEMA_VERSION",
    "Outcome",
    "PhaseOutcome",
    "ReportCollector",
    "ScenarioIdentity",
    "ScenarioRecord",
    "SuiteReport",
    "report_file_name",
]

REPORT_DIR_ENV = "PROVIDER_TCK_REPORT_DIR"
"""Names the directory a conformance report is written to.

An environment variable rather than a :class:`~.config.TckConfig` field, so that
emitting a report is a property of the *run* and not of the code: CI sets it, a
developer running the suite locally does not, and no adopter changes a line to
publish one. Each suite writes ``<dir>/<name>.json``, so several suites in one
pytest session -- flagd's RPC and in-process resolvers, say -- each produce their
own file without colliding.

Unset means no report, which is the default and is not an error.
"""

SCHEMA_VERSION = "1"
"""The major version of the report schema this emitter produces."""

TCK_IMPLEMENTATION = "python-sdk-contrib/tools/openfeature-provider-tck"
"""Which TCK implementation produced the report, as the schema spells it."""

PROVIDER_LANGUAGE = "python"

SDK_DISTRIBUTION = "openfeature-sdk"
TCK_DISTRIBUTION = "openfeature-provider-tck"

UNKNOWN = "unknown"
"""Stands in for an identity that could not be read.

Seven characters, which is the schema's minimum for ``tck.specRevision``, so a
build that could not reach git still emits a document that validates and says
plainly that it does not know rather than inventing a commit.
"""

_PACKAGE = "openfeature.contrib.tools.provider_tck"

_REVISION_FILE = "spec_revision.json"
"""Written at build time from the spec submodule; see ``hatch_build_sync.py``.

Read from a data file rather than the submodule because the submodule is not in
the published wheel: an adopter installing this package has no ``spec/``
directory to interrogate, and the revision the assets came from is exactly what
the report has to name.
"""

_TAG_PATTERN = re.compile(r"^[a-z0-9-]+$")
"""What the schema accepts as a tag, minus the leading at-sign.

Tags that do not match are dropped rather than emitted, because an invalid
document helps nobody; the canonical feature files carry none, so this only bites
a feature file that has been forked, which is itself worth noticing.
"""

_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


class Outcome(str, Enum):
    """The result of one scenario, or of one capability.

    Four rather than two, because "did not run" is not one thing. A capability
    the provider chose not to declare is a different statement from one the
    language makes impossible -- ``@strict-numeric-typing`` cannot hold in a
    language with no integer type -- and reporting both as not declared would
    show a whole language as missing something none of its providers can have.
    """

    PASSED = "passed"
    FAILED = "failed"
    NOT_DECLARED = "not-declared"
    NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True)
class ScenarioIdentity:
    """What a scenario is, independent of how it turned out.

    Established at collection, from the pytest-bdd node alone, so that a scenario
    skipped before a single step ran is identified exactly as fully as one that
    passed. That is what lets the report account for every scenario rather than
    only for the ones that got far enough to be interesting.
    """

    feature: str
    name: str
    tags: tuple[str, ...]
    example: tuple[tuple[str, str], ...] = ()
    """The Examples row, as header/cell pairs, for a scenario from an outline.

    Pairs rather than a mapping so that this stays hashable and ordered: the
    order is the feature file's column order, and the report carries it through
    rather than imposing one of its own.
    """

    def capabilities(self) -> tuple[Capability, ...]:
        """The capabilities this scenario's tags gate it behind."""
        gated = (capability_for_tag(tag) for tag in self.tags)
        return tuple(capability for capability in gated if capability is not None)


@dataclass
class ScenarioRecord:
    """One scenario's outcome, as the report will carry it."""

    feature: str
    """The feature file without its extension, e.g. ``errors``."""

    name: str
    tags: tuple[str, ...]
    outcome: Outcome
    example: tuple[tuple[str, str], ...] = ()
    """The Examples row this entry came from; empty for a scenario that is not
    an outline, in which case the field is omitted rather than emitted empty."""

    reason: str = ""
    duration_ms: float = 0.0

    def as_json(self) -> dict[str, typing.Any]:
        document: dict[str, typing.Any] = {
            "feature": self.feature,
            "name": self.name,
            "outcome": self.outcome.value,
        }
        if self.example:
            document["example"] = dict(self.example)
        if self.tags:
            document["tags"] = list(self.tags)
        if self.reason:
            document["reason"] = self.reason
        if self.duration_ms:
            document["durationMs"] = round(self.duration_ms, 3)
        return document


@dataclass
class SuiteReport:
    """What one suite -- one :class:`~.config.TckConfig` -- accumulates as it runs.

    Records are keyed by pytest node id rather than appended to a list, which is
    what makes "every scenario appears exactly once" a property of the structure
    instead of a promise made by the code that fills it. A scenario reports
    through several phases (setup, call, teardown) and each of them finds the
    same entry.
    """

    config: TckConfig
    provider_name: str | None = None
    records: dict[str, ScenarioRecord] = field(default_factory=dict)
    durations: dict[str, float] = field(default_factory=dict)

    def observe_provider_name(self, name: str) -> None:
        """Remember what the provider called itself through its own metadata.

        Last one wins, and they should all agree: a suite tests one provider.
        """
        if name:
            self.provider_name = name

    def add_duration(self, node_id: str, seconds: float) -> None:
        """Add one phase's time to a scenario's total.

        Kept apart from the record rather than added to it, because a scenario's
        first phase can take time before anything has decided its outcome, and
        time spent on a scenario that ended up skipped is still time.
        """
        self.durations[node_id] = self.durations.get(node_id, 0.0) + seconds * 1000.0

    def set_outcome(
        self,
        node_id: str,
        identity: ScenarioIdentity,
        outcome: Outcome,
        reason: str = "",
    ) -> None:
        """Record, or revise, one scenario's outcome.

        A failure is never revised away. A scenario whose steps passed and whose
        teardown then blew up is a failed scenario, and the phase that reports
        last must not be the one that decides.
        """
        record = self.records.get(node_id)
        if record is None:
            self.records[node_id] = ScenarioRecord(
                feature=identity.feature,
                name=identity.name,
                tags=identity.tags,
                outcome=outcome,
                example=identity.example,
                reason=reason,
            )
            return
        if record.outcome is Outcome.FAILED:
            return
        record.outcome = outcome
        record.reason = reason or record.reason

    @property
    def sorted_records(self) -> list[ScenarioRecord]:
        for node_id, record in self.records.items():
            record.duration_ms = self.durations.get(node_id, 0.0)
        # Sorted by the whole identity, example included, so that two rows of one
        # outline come out in a stable order rather than in whichever order the
        # dictionary happened to be filled.
        return sorted(
            self.records.values(), key=lambda r: (r.feature, r.name, r.example)
        )

    def counts(self) -> dict[str, int]:
        """Outcome tallies, for a log line and for the tests that check them."""
        tally: dict[str, int] = {}
        for record in self.records.values():
            tally[record.outcome.value] = tally.get(record.outcome.value, 0) + 1
        return tally

    def build(self) -> dict[str, typing.Any]:
        """Assemble the report document."""
        records = self.sorted_records
        spec_revision, assets_tree = spec_identity()

        tck: dict[str, typing.Any] = {
            "implementation": TCK_IMPLEMENTATION,
            "version": distribution_version(TCK_DISTRIBUTION),
            "specRevision": spec_revision,
        }
        if assets_tree:
            tck["assetsTree"] = assets_tree

        document: dict[str, typing.Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "provider": {
                # What the provider calls itself, not the suite name: the suite
                # name is chosen to read well in a failure message -- "flagd-rpc"
                # -- which makes it the configuration, and it is reported as one.
                # A provider with two materially different modes therefore
                # produces two reports that are not interchangeable.
                "name": self.provider_name or self.config.name,
                "language": PROVIDER_LANGUAGE,
                "configuration": self.config.name,
            },
            "sdk": {
                "name": SDK_DISTRIBUTION,
                "version": distribution_version(SDK_DISTRIBUTION),
            },
            "tck": tck,
            "capabilities": self._capabilities(records),
            "scenarios": [record.as_json() for record in records],
        }

        backend = self._backend()
        if backend:
            document["backend"] = backend
        return document

    def _backend(self) -> dict[str, typing.Any]:
        backend: dict[str, typing.Any] = {}
        description = getattr(self.config.control, "description", "")
        if isinstance(description, str) and description:
            backend["description"] = description
        control_api = control_api_of(self.config.control)
        if control_api:
            backend["controlApi"] = control_api
        return backend

    def _capabilities(
        self, records: list[ScenarioRecord]
    ) -> dict[str, dict[str, typing.Any]]:
        """Roll the per-scenario outcomes up to one verdict per capability.

        A capability is only reported as passed when everything gating on it
        actually passed, and only reported as not declared when the provider did
        not declare it -- in which case the reason says so, because "this
        provider does not support configuration-change events" is exactly what
        someone comparing providers came to find out.

        A capability the provider declared and *no scenario carries* is omitted
        rather than reported. ``@targeting`` is reserved: it exists in the
        vocabulary but nothing tests it, because asserting that an evaluation
        context reached the backend needs an echo operation the control API does
        not have. Reporting it as passed would be a green result for a claim
        nothing examined -- the vacuous pass the capability vocabulary exists to
        eliminate, arriving through the report rather than through the suite.
        Omitting beats inventing a fifth outcome: the four the schema allows are
        about what the provider did, and "the suite does not test this" is a fact
        about the suite.
        """
        # Counted rather than flagged, so that a failure can say how much of what
        # failed, and so that "no scenario exercises this at all" is a case the
        # rollup can see rather than one it silently reads as success.
        exercised: dict[Capability, int] = {}
        failed: dict[Capability, int] = {}
        for record in records:
            for tag in record.tags:
                capability = capability_for_tag(tag)
                if capability is None:
                    continue
                exercised[capability] = exercised.get(capability, 0) + 1
                if record.outcome is Outcome.FAILED:
                    failed[capability] = failed.get(capability, 0) + 1

        capabilities: dict[str, dict[str, typing.Any]] = {}
        for capability in Capability:
            if not self.config.declares(capability):
                capabilities[capability.tag] = {
                    "state": Outcome.NOT_DECLARED.value,
                    "reason": (
                        f"not declared by this provider's configuration; the "
                        f"{capability.tag} scenarios were skipped and did not "
                        f"contribute to this result"
                    ),
                }
            elif not exercised.get(capability):
                continue
            elif failed.get(capability):
                capabilities[capability.tag] = {
                    "state": Outcome.FAILED.value,
                    "reason": (
                        f"{failed[capability]} of {exercised[capability]} scenarios "
                        f"carrying {capability.tag} failed; the per-scenario results "
                        f"say which, and why"
                    ),
                }
            else:
                capabilities[capability.tag] = {"state": Outcome.PASSED.value}
        return capabilities


@dataclass(frozen=True)
class PhaseOutcome:
    """One pytest phase report, reduced to what the conformance report needs.

    Reduced rather than kept, because a :class:`pytest.TestReport` holds a
    formatted traceback and holding a session's worth of them to classify at the
    end would be a memory leak with a nice name.
    """

    when: str
    """``setup``, ``call`` or ``teardown``."""

    outcome: str
    """``passed``, ``failed`` or ``skipped``, as pytest decided."""

    xfail_reason: str | None = None
    """Set when pytest marked this an expected failure."""

    message: str = ""
    """The skip reason, or the failure's headline, already trimmed."""

    duration: float = 0.0


Classifier = typing.Callable[
    [PhaseOutcome, ScenarioIdentity, TckConfig], "tuple[Outcome, str] | None"
]


class ReportCollector:
    """Session-wide accumulator: which scenario belongs to which suite, and how it went.

    One pytest session can run several suites -- the TCK's own tests run two, and
    a provider with more than one resolver runs one per resolver -- so outcomes
    are attributed to a suite rather than to the session, and each suite writes
    its own file.

    Scenarios are enumerated at collection and resolved into records only at the
    end of the session. The order matters. A scenario skipped by a marker never
    runs a fixture, so a design that learned of a scenario when its fixtures ran
    would leave it out of the document entirely -- and a report that silently
    omits what it skipped satisfies "a skip is never reported as passed" while
    still misleading the person reading it.
    """

    def __init__(self) -> None:
        # Suites are keyed by the identity of their TckConfig, so two suites that
        # happen to share a name stay distinct here; that collision is caught
        # where it actually bites, when their file names turn out to be equal.
        self._suites: dict[int, SuiteReport] = {}
        self._suite_by_group: dict[str, SuiteReport] = {}
        self._collected: dict[str, tuple[str, ScenarioIdentity]] = {}
        self._phases: dict[str, list[PhaseOutcome]] = {}

    def collect(self, node_id: str, group: str, identity: ScenarioIdentity) -> None:
        """Note that this scenario exists, and which group of tests it came from.

        The group is the module the scenario was generated into. pytest-bdd's
        ``scenarios()`` injects its tests into the module that called it, and a
        module resolves one ``tck_config``, so the module is what says which
        suite a scenario belongs to -- and it says so without running anything.
        """
        self._collected[node_id] = (group, identity)

    def observe(self, node_id: str, phase: PhaseOutcome) -> None:
        """Record one phase's result for a scenario, if it is one of ours."""
        if node_id in self._collected:
            self._phases.setdefault(node_id, []).append(phase)

    def bind(self, node_id: str, config: TckConfig) -> None:
        """Learn which suite a group of scenarios is testing.

        Called from a fixture, because the ``TckConfig`` is a fixture value and
        there is no way to know it without asking for it. Only one scenario of a
        group has to get this far for the whole group to be attributed.
        """
        entry = self._collected.get(node_id)
        if entry is not None:
            self._suite_by_group[entry[0]] = self.suite_for(config)

    def suite_for(self, config: TckConfig) -> SuiteReport:
        return self._suites.setdefault(id(config), SuiteReport(config=config))

    @property
    def suites(self) -> list[SuiteReport]:
        return list(self._suites.values())

    def resolve(self, classify: Classifier) -> list[str]:
        """Turn the collected phases into records, and report what could not be.

        Returns the problems, one string each, and they are meant to be shouted
        about rather than logged: a scenario that ran but is missing from the
        document is the one failure mode this format exists to rule out.
        """
        problems: list[str] = []
        for node_id, (group, identity) in sorted(self._collected.items()):
            suite = self._suite_by_group.get(group)
            if suite is None:
                problems.append(
                    f"{node_id}: no TckConfig was resolved for {group}, so its "
                    f"outcome belongs to no suite and is missing from every report"
                )
                continue
            phases = self._phases.get(node_id)
            if not phases:
                problems.append(
                    f"{node_id}: was collected but never ran, so the report for "
                    f"{suite.config.name!r} does not account for it"
                )
                continue
            for phase in phases:
                classified = classify(phase, identity, suite.config)
                if classified is not None:
                    outcome, reason = classified
                    suite.set_outcome(node_id, identity, outcome, reason)
                suite.add_duration(node_id, phase.duration)
        return problems


def control_api_of(control: object) -> str:
    """Report how the backend was driven, if the control says.

    Read off an optional attribute rather than added to the
    :class:`~.control.BackendControl` protocol, because a protocol member would
    make every existing control incomplete for the sake of one string. A control
    that does not offer it simply omits the field, which is the honest answer:
    the TCK cannot infer from the outside whether a control spoke the normative
    HTTP API or reached into the process.
    """
    value = getattr(control, "control_api", None)
    if isinstance(value, str) and value in {"http", "in-process"}:
        return value
    return ""


def normalise_tags(tags: typing.Iterable[str]) -> tuple[str, ...]:
    """Turn Gherkin tags as pytest-bdd holds them into the form the schema wants.

    pytest-bdd strips the leading at-sign; the schema requires it back.
    """
    return tuple(sorted(f"@{tag}" for tag in tags if _TAG_PATTERN.match(tag)))


def report_file_name(suite_name: str) -> str:
    """Turn a suite name into a file name.

    Suite names are chosen to read well in a failure message rather than to be
    path-safe, so anything not obviously safe becomes a hyphen. Without this a
    suite named ``flagd/rpc`` would quietly write outside the directory it was
    given.
    """
    cleaned = _UNSAFE_IN_FILENAME.sub("-", suite_name).strip("-.")
    return f"{cleaned or 'report'}.json"


def write_report(
    directory: Path, suite_name: str, document: dict[str, typing.Any]
) -> Path:
    """Write one report, returning where it went."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / report_file_name(suite_name)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def distribution_version(distribution: str) -> str:
    """Read an installed distribution's version.

    Read rather than declared, because a declared version is a second place to
    be wrong: the report would go on claiming 0.8.2 after a dependency bump moved
    the actual code underneath it.
    """
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return UNKNOWN


def spec_identity() -> tuple[str, str]:
    """Return the spec commit and asset tree these feature files came from.

    Captured at build time rather than read here, because the submodule that
    holds the answer is not in the wheel. A build that could not reach git says
    so with :data:`UNKNOWN` instead of inventing a commit, and an installation
    old enough to predate the generated file degrades the same way rather than
    failing to emit a report at all.
    """
    reference = importlib.resources.files(_PACKAGE) / _REVISION_FILE
    try:
        data = json.loads(reference.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UNKNOWN, ""
    if not isinstance(data, dict):
        return UNKNOWN, ""
    revision = data.get("specRevision")
    tree = data.get("assetsTree")
    return (
        revision if isinstance(revision, str) and len(revision) >= 7 else UNKNOWN,
        tree if isinstance(tree, str) and re.fullmatch(r"[0-9a-f]{40}", tree) else "",
    )
