"""The conformance report envelope: what was tested, what it claims, where the results are.

A run of the suite produces a pass or a fail on a terminal, which is enough for
the person who started it and useless to anyone else. The report is the same run
written down in a form something other than a human can read -- a comparison
page, an aggregator, a release gate -- against a schema owned by the
specification rather than by this package, so that four languages emit the same
document.

This document no longer describes the results. It is an envelope that identifies
the subject and points at a :mod:`Cucumber Messages <.messages>` stream beside
it. The per-scenario outcome list, the outcome enum and the field naming which
Scenario Outline row an entry came from have all been deleted, because Messages
already carries every one of them -- along with the executed feature source,
which no bespoke format had.

Two things stay here, because Messages has no slot for either.

The **declaration** is an input to reading the results rather than a summary of
them. A skipped scenario in the stream says the question was not put to this
provider; only the declaration says whether that is because the provider
declines the capability. Given the declaration and a scenario's tags -- both
present -- the reason for a skip follows, so it no longer has to be transported
once per scenario.

The **tested subject**: no standard results format has a slot for "the provider
under test". Messages records the runtime and the OS, which is what produced the
answers, not what was being asked about.

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
from pathlib import Path

from .config import TckConfig
from .messages import (
    MESSAGES_FORMAT,
    ScenarioIdentity,
    ScenarioRun,
    StepRun,
    messages_protocol_version,
)

__all__ = [
    "REPORT_DIR_ENV",
    "SCHEMA_VERSION",
    "PhaseOutcome",
    "ReportCollector",
    "Results",
    "SuiteReport",
    "envelope_file_name",
    "stream_file_name",
]

REPORT_DIR_ENV = "PROVIDER_TCK_REPORT_DIR"
"""Names the directory a conformance report is written to.

An environment variable rather than a :class:`~.config.TckConfig` field, so that
emitting a report is a property of the *run* and not of the code: CI sets it, a
developer running the suite locally does not, and no adopter changes a line to
publish one. Each suite writes two files -- ``<dir>/<name>.json``, the envelope,
and ``<dir>/<name>.ndjson``, the results the envelope points at -- so several
suites in one pytest session, flagd's RPC and in-process resolvers say, each
produce their own pair without colliding.

Unset means no report, which is the default and is not an error.
"""

SCHEMA_VERSION = "1"
"""The major version of the report schema this emitter produces."""

TCK_IMPLEMENTATION = "python-sdk-contrib/tools/openfeature-tck"
"""Which TCK implementation produced the report, as the schema spells it."""

PROVIDER_LANGUAGE = "python"

SDK_DISTRIBUTION = "openfeature-sdk"
TCK_DISTRIBUTION = "openfeature-tck"

UNKNOWN = "unknown"
"""Stands in for an identity that could not be read.

Seven characters, which is the schema's minimum for ``tck.specRevision``, so a
build that could not reach git still emits a document that validates and says
plainly that it does not know rather than inventing a commit.
"""

_PACKAGE = "openfeature.contrib.tools.tck"

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


@dataclass(frozen=True)
class Results:
    """Where the executed results are, and what covers them."""

    location: str
    digest: str
    format: str = MESSAGES_FORMAT

    def as_json(self) -> dict[str, typing.Any]:
        # The format's version is recorded alongside its name because Cucumber
        # Messages is versioned and the four implementations pin different
        # releases. Without it a consumer validating this stream has to guess
        # which schema to use, and guessing wrong is worse than not checking: a
        # later schema accepts messages this producer could not have emitted,
        # and an earlier one rejects messages that are perfectly valid.
        document = {
            "format": self.format,
            "formatVersion": messages_protocol_version(),
            "location": self.location,
        }
        if self.digest:
            document["digest"] = self.digest
        return document


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

    start: float = 0.0
    stop: float = 0.0


Resolver = typing.Callable[
    [ScenarioIdentity, "list[PhaseOutcome]", "list[StepRun]"], ScenarioRun
]
"""Turns what pytest reported about one scenario into what the stream records.

A callable rather than a method, because the mapping is entirely about pytest --
which phase means what, and that an expected failure is still a failure -- and
this module deliberately knows nothing about pytest.
"""


@dataclass
class SuiteReport:
    """What one suite -- one :class:`~.config.TckConfig` -- accumulates as it runs.

    Runs are keyed by pytest node id rather than appended to a list, which is
    what makes "every scenario appears exactly once" a property of the structure
    instead of a promise made by the code that fills it.
    """

    config: TckConfig
    provider_name: str | None = None
    runs: dict[str, ScenarioRun] = field(default_factory=dict)

    def observe_provider_name(self, name: str) -> None:
        """Remember what the provider called itself through its own metadata.

        Last one wins, and they should all agree: a suite tests one provider.
        """
        if name:
            self.provider_name = name

    def record(self, node_id: str, run: ScenarioRun) -> None:
        self.runs[node_id] = run

    @property
    def sorted_runs(self) -> list[ScenarioRun]:
        """The runs in a stable order: feature, then scenario, then row.

        Sorted by the whole identity, the Examples row included, so that two rows
        of one outline reach the stream in the feature file's terms rather than
        in whichever order the dictionary happened to be filled.
        """
        return sorted(
            self.runs.values(),
            key=lambda run: (
                run.identity.uri,
                run.identity.name,
                run.identity.example,
            ),
        )

    def counts(self) -> dict[str, int]:
        """Status tallies, for a log line and for the tests that check them."""
        tally: dict[str, int] = {}
        for run in self.runs.values():
            key = run.status.value.lower()
            tally[key] = tally.get(key, 0) + 1
        return tally

    def build(self, results: Results) -> dict[str, typing.Any]:
        """Assemble the envelope around a results payload already written."""
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
            "tck": {
                "implementation": TCK_IMPLEMENTATION,
                "version": distribution_version(TCK_DISTRIBUTION),
                "specRevision": spec_revision(),
            },
            "declaration": self._declaration(),
            "results": results.as_json(),
        }

        # Always emitted, never conditionally: the schema requires `backend`
        # at the top level and `controlApi` within it, because a provider with
        # no backend still had its flag state manipulated somehow and which of
        # the two ways that was is what the rest of the document is worth.
        document["backend"] = self._backend()
        deviations = [deviation.as_json() for deviation in self.config.known_deviations]
        if deviations:
            # Omitted rather than emitted empty: stating no deviations is a
            # claim, and an emitter that always emitted the field would make that
            # claim on every provider's behalf whether or not it had checked.
            document["knownDeviations"] = deviations
        return document

    def _declaration(self) -> dict[str, typing.Any]:
        """What the provider claims, which is what makes a skip legible.

        A skip in the payload says only that the question was not put to this
        provider; this says whether that is because the capability was not
        claimed. Given the two, the reason a scenario was skipped follows from
        its own tags, which is why one skip carrying its reason is the whole
        mechanism and nothing here restates it.

        The set is not filtered. A reserved capability -- one no scenario
        carries, which the schema forbids in this block -- cannot be in a
        ``TckConfig`` at all: it is refused at construction, and the default
        capability set excludes it. Dropping one silently at emission time would
        make a rejected configuration look like an accepted one, and leave the
        adopter who wrote it believing the declaration they read back was the
        declaration they asked for.
        """
        return {"declared": self.config.sorted_capabilities}

    def _backend(self) -> dict[str, typing.Any]:
        """What was driven, and which of the two paths drove it.

        ``controlApi`` is read straight off the control, which the
        :class:`~.control.BackendControl` protocol requires it to answer -- so
        there is nothing to fall back to and nothing to infer. That is the
        point: nothing outside a control can tell whether it spoke the
        normative HTTP API or reached into this process, so a harness that
        guessed would be right about the two controls this package ships and
        silently wrong about an adopter's custom one, which is the case where
        the answer matters.

        ``description`` is free text for a person and the schema leaves it
        optional, so an empty one is left out rather than emitted blank.
        """
        backend: dict[str, typing.Any] = {"controlApi": self.config.control.control_api}
        description = self.config.control.description
        if description:
            backend["description"] = description
        return backend


class ReportCollector:
    """Session-wide accumulator: which scenario belongs to which suite, and how it went.

    One pytest session can run several suites -- the TCK's own tests run two, and
    a provider with more than one resolver runs one per resolver -- so outcomes
    are attributed to a suite rather than to the session, and each suite writes
    its own pair of files.

    Scenarios are enumerated at collection and resolved into runs only at the end
    of the session. The order matters. A scenario skipped by a marker never runs
    a fixture, so a design that learned of a scenario when its fixtures ran would
    leave it out of the stream entirely -- and a report that silently omits what
    it skipped satisfies "a skip is never reported as passed" while still
    misleading the person reading it.
    """

    def __init__(self) -> None:
        # Suites are keyed by the identity of their TckConfig, so two suites that
        # happen to share a name stay distinct here; that collision is caught
        # where it actually bites, when their file names turn out to be equal.
        self._suites: dict[int, SuiteReport] = {}
        self._suite_by_group: dict[str, SuiteReport] = {}
        self._collected: dict[str, tuple[str, ScenarioIdentity]] = {}
        self._phases: dict[str, list[PhaseOutcome]] = {}
        self._steps: dict[str, list[StepRun]] = {}

    def collect(self, node_id: str, group: str, identity: ScenarioIdentity) -> None:
        """Note that this scenario exists, and which group of tests it came from.

        The group is the module the scenario was generated into. pytest-bdd's
        ``scenarios()`` injects its tests into the module that called it, and a
        module resolves one ``tck_config``, so the module is what says which
        suite a scenario belongs to -- and it says so without running anything.
        """
        self._collected[node_id] = (group, identity)

    @property
    def identities(self) -> list[ScenarioIdentity]:
        """Every collected scenario, so the feature files can be parsed once."""
        return [identity for _, identity in self._collected.values()]

    def observe(self, node_id: str, phase: PhaseOutcome) -> None:
        """Record one phase's result for a scenario, if it is one of ours."""
        if node_id in self._collected:
            self._phases.setdefault(node_id, []).append(phase)

    def observe_step(self, node_id: str, step: StepRun) -> None:
        """Record what one Gherkin step did, in execution order.

        Recorded as it happens rather than reconstructed afterwards, because
        pytest reports a scenario and not its steps: only the runner knows which
        step of eight failed, and a stream that marked all eight failed would be
        saying something untrue about seven of them.
        """
        self._steps.setdefault(node_id, []).append(step)

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

    def resolve(self, resolver: Resolver) -> list[str]:
        """Turn the collected phases into runs, and report what could not be.

        Returns the problems, one string each, and they are meant to be shouted
        about rather than logged: a scenario that ran but is missing from the
        stream is the one failure mode this format exists to rule out.
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
            suite.record(
                node_id, resolver(identity, phases, self._steps.get(node_id, []))
            )
        return problems


# NEITHER ``control_api_of`` NOR ``control_api_gap`` EXISTS ANY MORE
#
# Both were consequences of the field being optional. One read it off duck-typed
# with an empty-string fallback; the other described, in the run output, a
# control that had declined to say -- because omission was otherwise invisible:
# the suite passed, the report validated, and the field was simply absent.
#
# ``control_api`` is now a required member of ``BackendControl`` and the schema
# requires the field, so there is no silence left to detect and no fallback left
# to take. The type assertion and the empty-string branch both stop existing,
# which is a net deletion rather than a move.


def normalise_tags(tags: typing.Iterable[str]) -> tuple[str, ...]:
    """Turn Gherkin tags as pytest-bdd holds them into the form the schema wants.

    pytest-bdd strips the leading at-sign; the schema requires it back.
    """
    return tuple(sorted(f"@{tag}" for tag in tags if _TAG_PATTERN.match(tag)))


def report_stem(suite_name: str) -> str:
    """Turn a suite name into a file name stem.

    Suite names are chosen to read well in a failure message rather than to be
    path-safe, so anything not obviously safe becomes a hyphen. Without this a
    suite named ``flagd/rpc`` would quietly write outside the directory it was
    given.
    """
    cleaned = _UNSAFE_IN_FILENAME.sub("-", suite_name).strip("-.")
    return cleaned or "report"


def envelope_file_name(suite_name: str) -> str:
    return f"{report_stem(suite_name)}.json"


def stream_file_name(suite_name: str) -> str:
    """The results payload, beside the envelope that points at it.

    A sibling rather than a subdirectory so that ``results.location`` is a bare
    file name, which is a relative reference that survives the whole pair being
    moved, uploaded or served from somewhere other than where it was written.
    """
    return f"{report_stem(suite_name)}.ndjson"


def write_envelope(
    directory: Path, suite_name: str, document: dict[str, typing.Any]
) -> Path:
    """Write one envelope, returning where it went."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / envelope_file_name(suite_name)
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


def spec_revision() -> str:
    """Return the spec commit these feature files came from.

    Captured at build time rather than read here, because the submodule that
    holds the answer is not in the wheel. A build that could not reach git says
    so with :data:`UNKNOWN` instead of inventing a commit, and an installation
    old enough to predate the generated file degrades the same way rather than
    failing to emit a report at all.

    The asset tree hash that used to accompany it is gone. It was carried so that
    a consumer could tell whether two runs executed the same questions; the
    results payload now carries the executed feature source itself, which answers
    that directly rather than by proxy.
    """
    reference = importlib.resources.files(_PACKAGE) / _REVISION_FILE
    try:
        data = json.loads(reference.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UNKNOWN
    if not isinstance(data, dict):
        return UNKNOWN
    revision = data.get("specRevision")
    return revision if isinstance(revision, str) and len(revision) >= 7 else UNKNOWN
