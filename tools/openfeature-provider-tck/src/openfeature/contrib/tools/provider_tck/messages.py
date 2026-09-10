"""The results payload: one run of the suite written as Cucumber Messages.

The conformance report used to define its own per-scenario result list -- an
outcome enum, a tag list, and a field naming which Scenario Outline row an entry
came from. All three already exist in `Cucumber Messages`_, the ndjson protocol
Cucumber itself emits: it is maintained, schema'd, cross-language, and it carries
things a bespoke format would have had to invent, including the executed feature
source. So the report no longer describes results. It points at a stream of them.

Nothing here knows about pytest. It takes a set of scenario outcomes and a set of
feature files and produces the stream; :mod:`.emitter` is what turns a pytest
session into the former.

**Where the messages come from.** Two libraries, each doing the half it owns.

``gherkin-official`` -- the reference Gherkin parser, already a dependency of
pytest-bdd -- produces the ``gherkinDocument`` and ``pickle`` payloads. Those
payloads *are* Messages: emitting Messages ndjson is what that library exists
for, so its output is used as it comes rather than round-tripped through
another representation that could quietly drop a field it does not model.

``cucumber-messages`` -- the official Python types, from the same repository as
the protocol -- builds the execution half: ``Meta``, ``TestCase``,
``TestCaseStarted``, ``TestStepFinished`` and the rest. Hand-writing those dicts
would work until the protocol moved.

**Why the feature files are parsed again.** pytest-bdd parses them with
``gherkin-official`` too, but converts the result into dataclasses of its own
that do not carry the AST node ids. Those ids are what a pickle refers to, and
what makes one Scenario Outline row distinguishable from another, so the stream
needs a parse whose ids it owns. Four small files, parsed once per session.

.. _Cucumber Messages: https://github.com/cucumber/messages
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import typing
from dataclasses import dataclass, field
from pathlib import Path, PurePath

import cucumber_messages as cucumber
from gherkin.ast_builder import AstBuilder
from gherkin.parser import Parser
from gherkin.pickles.compiler import Compiler
from gherkin.stream.id_generator import IdGenerator

from .capability import Capability, capability_for_tag

__all__ = [
    "MESSAGES_FORMAT",
    "FeatureCatalog",
    "ScenarioIdentity",
    "ScenarioRun",
    "Status",
    "StepRun",
    "worse",
    "write_stream",
]

MESSAGES_FORMAT = "cucumber-messages"
"""The ``results.format`` value the envelope carries for this payload."""

Status = cucumber.TestStepResultStatus
"""The protocol's own status vocabulary, used rather than one of ours.

Cucumber's seven statuses already draw the distinctions a conformance run needs,
and the four-value outcome enum this replaced drew a different set: it split
"did not run" into a capability the provider did not declare and one that cannot
apply to it, and merged "failed" with "the step was never reached". The first
distinction is not a property of the run at all -- it follows from the report's
declaration and the scenario's tags -- so it belongs in the envelope, once, and
not in every scenario.
"""

_SEVERITY = {
    Status.unknown: 0,
    Status.passed: 1,
    Status.skipped: 2,
    Status.pending: 3,
    Status.undefined: 4,
    Status.ambiguous: 5,
    Status.failed: 6,
}
"""How Cucumber orders its statuses, which is how a test case takes one.

A test case is as bad as its worst step -- that is the rule a consumer applies to
derive a scenario's outcome from the stream, and this module applies the same one
so that what the stream says and what this package believes cannot diverge.
"""


def worse(left: Status, right: Status) -> Status:
    """The more serious of two statuses."""
    return right if _SEVERITY[right] > _SEVERITY[left] else left


_MEDIA_TYPE = cucumber.SourceMediaType.text_x_cucumber_gherkin_plain

_SETUP_HOOK_ID = "provider-tck-setup"
_TEARDOWN_HOOK_ID = "provider-tck-teardown"
"""The two hooks every test case carries, as the protocol models them.

pytest runs a scenario in three phases and only the middle one executes Gherkin
steps: the capability gate skips during setup, and a provider that fails to shut
down fails during teardown. Neither has a pickle step to attach a result to, so
without hooks a gated skip would have to borrow the first step's result and a
teardown failure would be invisible behind a row of passed steps. Cucumber
represents exactly this with a ``Hook`` and a ``TestStep`` that references it,
which is what these are.
"""

_MESSAGES_DISTRIBUTION = "cucumber-messages"
_UNKNOWN_VERSION = "unknown"


@dataclass(frozen=True)
class ScenarioIdentity:
    """What a scenario is, independent of how it turned out.

    Established at collection, from the pytest node alone, so that a scenario
    skipped before a single step ran is identified exactly as fully as one that
    passed. That is what lets the stream account for every scenario rather than
    only for the ones that got far enough to be interesting.
    """

    uri: str
    """The feature file as Cucumber names it, e.g. ``features/errors.feature``.

    Slash-separated on every platform, and the same string in ``Source``,
    ``GherkinDocument`` and ``Pickle``, which is what ties the three together.
    """

    path: Path
    """Where that file actually is, so its source can be read and parsed."""

    name: str
    """The scenario name as the feature file spells it.

    For a Scenario Outline this is the template name, shared by every row --
    which is why it is not on its own an identity.
    """

    tags: tuple[str, ...]

    example: tuple[tuple[str, str], ...] = ()
    """The Examples row, as header/cell pairs, for a scenario from an outline.

    Not reported: Messages carries row identity as the pickle's AST node ids,
    which is where four independent implementations of a bespoke ``example``
    field were each converging by hand. It survives here only as the join key
    that matches a pytest node to its pickle -- pytest-bdd parametrises the
    generated test over the row, and the row is the one thing both sides of that
    join can see.
    """

    def capabilities(self) -> tuple[Capability, ...]:
        """The capabilities this scenario's tags gate it behind."""
        gated = (capability_for_tag(tag) for tag in self.tags)
        return tuple(capability for capability in gated if capability is not None)


@dataclass(frozen=True)
class StepRun:
    """What happened to one step, as the protocol records it."""

    status: Status
    message: str = ""
    exception_type: str = ""
    started_ns: int = 0
    finished_ns: int = 0


@dataclass
class ScenarioRun:
    """One scenario's execution: its verdict, and what each phase did."""

    identity: ScenarioIdentity
    status: Status = Status.unknown
    message: str = ""
    setup: StepRun | None = None
    teardown: StepRun | None = None
    steps: list[StepRun] = field(default_factory=list)
    """Step results in execution order, as far as execution got.

    Shorter than the pickle's step list whenever a scenario stopped early, which
    is the normal case for a failure and the whole list for a skip. The stream
    pads the difference with ``SKIPPED``, which is what Cucumber means by it.
    """

    started_ns: int = 0
    finished_ns: int = 0


@dataclass(frozen=True)
class _Pickle:
    """One compiled pickle, reduced to what the stream needs to refer to it."""

    id: str
    step_ids: tuple[str, ...]
    payload: dict[str, typing.Any]


class FeatureCatalog:
    """The feature files a run executed, parsed into Messages and indexed.

    Indexed by what both sides of the join can see: the file, the scenario name
    as the feature file spells it, and the Examples row. A pytest-bdd node knows
    those three; a pickle can be made to yield them by following its AST node ids
    back to the scenario and the table row it was compiled from. Matching on the
    pickle's own name would not do, because the compiler interpolates outline
    parameters into it and pytest-bdd does not.
    """

    def __init__(self) -> None:
        # One generator across the whole session, so ids are unique across
        # feature files rather than only within one -- a stream is a single id
        # space and two files numbering from zero would collide.
        self._ids = IdGenerator()
        self._sources: dict[str, str] = {}
        self._documents: dict[str, dict[str, typing.Any]] = {}
        self._pickles: dict[str, list[_Pickle]] = {}
        self._index: dict[tuple[str, str, tuple[tuple[str, str], ...]], _Pickle] = {}

    @property
    def uris(self) -> list[str]:
        return sorted(self._documents)

    def load(self, identity: ScenarioIdentity) -> None:
        """Parse the feature file this scenario came from, once."""
        if identity.uri in self._documents:
            return
        source = identity.path.read_text(encoding="utf-8")
        document: dict[str, typing.Any] = Parser(
            ast_builder=AstBuilder(self._ids)
        ).parse(source)
        document["uri"] = identity.uri
        pickles: list[dict[str, typing.Any]] = Compiler(self._ids).compile(document)

        self._sources[identity.uri] = source
        self._documents[identity.uri] = document
        self._pickles[identity.uri] = [
            _Pickle(
                id=str(pickle["id"]),
                step_ids=tuple(str(step["id"]) for step in pickle.get("steps") or ()),
                payload=pickle,
            )
            for pickle in pickles
        ]
        self._index_pickles(identity.uri, document, pickles)

    def _index_pickles(
        self,
        uri: str,
        document: dict[str, typing.Any],
        pickles: list[dict[str, typing.Any]],
    ) -> None:
        names, rows = _ast_index(document)
        for pickle, entry in zip(pickles, self._pickles[uri], strict=True):
            ast_node_ids = [str(node) for node in pickle["astNodeIds"]]
            name = names.get(ast_node_ids[0], str(pickle["name"]))
            row = rows.get(ast_node_ids[1], ()) if len(ast_node_ids) > 1 else ()
            self._index.setdefault((uri, name, row), entry)

    def pickle_for(self, identity: ScenarioIdentity) -> _Pickle | None:
        """The pickle this scenario was compiled from, or ``None`` if unmatched.

        ``None`` is a defect rather than a possibility to tolerate: a scenario
        that ran and has no pickle cannot appear in the stream, which is the one
        failure mode the report exists to rule out. The caller fails the run.
        """
        return self._index.get((identity.uri, identity.name, identity.example))

    def source_envelopes(self) -> typing.Iterator[dict[str, typing.Any]]:
        """The ``Source``, ``GherkinDocument`` and ``Pickle`` messages, in order.

        The source comes first because everything after it refers to it, and it
        is the reason this format beats recording an asset revision: a consumer
        can read the questions that were actually asked rather than trusting a
        commit hash to stand for them.
        """
        for uri in self.uris:
            yield _envelope(
                cucumber.Envelope(
                    source=cucumber.Source(
                        data=self._sources[uri], media_type=_MEDIA_TYPE, uri=uri
                    )
                )
            )
            yield {"gherkinDocument": self._documents[uri]}
            for entry in self._pickles[uri]:
                yield {"pickle": entry.payload}


def _ast_index(
    document: dict[str, typing.Any],
) -> tuple[dict[str, str], dict[str, tuple[tuple[str, str], ...]]]:
    """Map AST node ids onto scenario names and Examples rows.

    Walks the parsed document rather than the pickles, because the pickle is
    where the outline has already been expanded: the scenario name it carries has
    the row's parameters substituted into it, and the row itself has become a
    list of interpolated step texts. The AST still has both separately, which is
    what a pytest-bdd node can be compared against.
    """
    names: dict[str, str] = {}
    rows: dict[str, tuple[tuple[str, str], ...]] = {}

    def visit(children: typing.Iterable[dict[str, typing.Any]]) -> None:
        for child in children:
            if "rule" in child:
                visit(child["rule"].get("children") or ())
                continue
            scenario = child.get("scenario")
            if scenario is None:
                continue
            names[str(scenario["id"])] = str(scenario["name"])
            for examples in scenario.get("examples") or ():
                header = examples.get("tableHeader")
                if header is None:
                    continue
                headers = [str(cell["value"]) for cell in header["cells"]]
                for row in examples.get("tableBody") or ():
                    cells = [str(cell["value"]) for cell in row["cells"]]
                    rows[str(row["id"])] = tuple(zip(headers, cells, strict=False))

    feature = document.get("feature")
    if feature is not None:
        visit(feature.get("children") or ())
    return names, rows


def write_stream(
    path: Path,
    catalog: FeatureCatalog,
    runs: typing.Sequence[ScenarioRun],
    implementation: str,
    implementation_version: str,
) -> str:
    """Write the stream and return its digest as ``sha256:<hex>``.

    The digest is returned rather than recomputed by the caller so that what is
    hashed is exactly the bytes that were written, which is the only version of
    that claim worth putting in the envelope.
    """
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for envelope in _stream(catalog, runs, implementation, implementation_version):
            line = (
                json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n"
            )
            stream.write(line)
            digest.update(line.encode("utf-8"))
    return f"sha256:{digest.hexdigest()}"


def _stream(
    catalog: FeatureCatalog,
    runs: typing.Sequence[ScenarioRun],
    implementation: str,
    implementation_version: str,
) -> typing.Iterator[dict[str, typing.Any]]:
    started = min((run.started_ns for run in runs), default=0)
    finished = max((run.finished_ns for run in runs), default=started)

    yield _envelope(
        cucumber.Envelope(meta=_meta(implementation, implementation_version))
    )
    yield _envelope(
        cucumber.Envelope(
            test_run_started=cucumber.TestRunStarted(
                id=_RUN_ID, timestamp=_timestamp(started)
            )
        )
    )
    yield from _hook_envelopes()
    yield from catalog.source_envelopes()

    for index, run in enumerate(runs):
        entry = catalog.pickle_for(run.identity)
        if entry is None:
            # Ruled out by the caller before it gets here; skipping rather than
            # raising keeps a defect in the report from destroying the run's own
            # exit status, which says something the report cannot.
            continue
        yield from _test_case_envelopes(f"test-case-{index}", entry, run)

    yield _envelope(
        cucumber.Envelope(
            test_run_finished=cucumber.TestRunFinished(
                success=all(run.status is not Status.failed for run in runs),
                timestamp=_timestamp(finished),
                test_run_started_id=_RUN_ID,
            )
        )
    )


_RUN_ID = "provider-tck-run"


def _test_case_envelopes(
    test_case_id: str, entry: _Pickle, run: ScenarioRun
) -> typing.Iterator[dict[str, typing.Any]]:
    """One scenario: its test case, and what each of its steps did."""
    started_id = f"{test_case_id}-started"
    setup_step_id = f"{test_case_id}-setup"
    teardown_step_id = f"{test_case_id}-teardown"

    test_steps = [
        cucumber.TestStep(id=setup_step_id, hook_id=_SETUP_HOOK_ID),
        *(
            cucumber.TestStep(id=f"{test_case_id}-{position}", pickle_step_id=step_id)
            for position, step_id in enumerate(entry.step_ids)
        ),
        cucumber.TestStep(id=teardown_step_id, hook_id=_TEARDOWN_HOOK_ID),
    ]
    yield _envelope(
        cucumber.Envelope(
            test_case=cucumber.TestCase(
                id=test_case_id,
                pickle_id=entry.id,
                test_run_started_id=_RUN_ID,
                test_steps=test_steps,
            )
        )
    )
    yield _envelope(
        cucumber.Envelope(
            test_case_started=cucumber.TestCaseStarted(
                attempt=0,
                id=started_id,
                test_case_id=test_case_id,
                timestamp=_timestamp(run.started_ns),
            )
        )
    )

    for step_id, result in zip(
        (step.id for step in test_steps), _step_runs(entry, run), strict=True
    ):
        yield from _step_envelopes(started_id, step_id, result)

    yield _envelope(
        cucumber.Envelope(
            test_case_finished=cucumber.TestCaseFinished(
                test_case_started_id=started_id,
                timestamp=_timestamp(run.finished_ns),
                will_be_retried=False,
            )
        )
    )


def _step_runs(entry: _Pickle, run: ScenarioRun) -> list[StepRun]:
    """Every step of the pickle and both hooks, including what never ran.

    A scenario that stopped early -- the ordinary shape of both a failure and a
    skip -- has fewer recorded results than the pickle has steps, and the
    remainder are reported ``SKIPPED``, which is what Cucumber means by it and
    what makes the stream account for the whole scenario rather than the part of
    it that executed.

    The last thing this does is make sure the scenario's own verdict survives the
    trip. A consumer reads a test case's outcome as the worst of its steps, so a
    verdict no step accounts for would be lost: a strict ``xfail`` that passed is
    a failed scenario every one of whose steps passed, and there are other ways
    for a runner to fail a test case between its steps. Whatever is left over is
    attached to the after-hook, which is where a test case failing outside its
    own steps belongs.
    """
    unreached = StepRun(
        status=Status.skipped,
        started_ns=run.finished_ns,
        finished_ns=run.finished_ns,
    )
    steps = list(run.steps[: len(entry.step_ids)])
    steps += [unreached] * (len(entry.step_ids) - len(steps))
    setup = run.setup or StepRun(
        status=Status.passed,
        started_ns=run.started_ns,
        finished_ns=run.started_ns,
    )
    teardown = run.teardown or StepRun(
        status=Status.passed,
        started_ns=run.finished_ns,
        finished_ns=run.finished_ns,
    )

    reported = Status.unknown
    for result in (setup, *steps, teardown):
        reported = worse(reported, result.status)
    if worse(reported, run.status) is not reported:
        teardown = StepRun(
            status=run.status,
            message=run.message,
            started_ns=teardown.started_ns,
            finished_ns=teardown.finished_ns,
        )
    return [setup, *steps, teardown]


def _step_envelopes(
    started_id: str, step_id: str, result: StepRun
) -> typing.Iterator[dict[str, typing.Any]]:
    yield _envelope(
        cucumber.Envelope(
            test_step_started=cucumber.TestStepStarted(
                test_case_started_id=started_id,
                test_step_id=step_id,
                timestamp=_timestamp(result.started_ns),
            )
        )
    )
    exception = (
        cucumber.Exception(type=result.exception_type, message=result.message or None)
        if result.exception_type
        else None
    )
    yield _envelope(
        cucumber.Envelope(
            test_step_finished=cucumber.TestStepFinished(
                test_case_started_id=started_id,
                test_step_id=step_id,
                test_step_result=cucumber.TestStepResult(
                    duration=_duration(result.finished_ns - result.started_ns),
                    status=result.status,
                    message=result.message or None,
                    exception=exception,
                ),
                timestamp=_timestamp(result.finished_ns),
            )
        )
    )


def _hook_envelopes() -> typing.Iterator[dict[str, typing.Any]]:
    for hook_id, hook_type, name in (
        (
            _SETUP_HOOK_ID,
            cucumber.HookType.before_test_case,
            "provider-tck setup: capability gate, provider registration",
        ),
        (
            _TEARDOWN_HOOK_ID,
            cucumber.HookType.after_test_case,
            "provider-tck teardown: provider shutdown",
        ),
    ):
        yield _envelope(
            cucumber.Envelope(
                hook=cucumber.Hook(
                    id=hook_id,
                    name=name,
                    type=hook_type,
                    source_reference=cucumber.SourceReference(
                        uri="openfeature/contrib/tools/provider_tck/plugin.py"
                    ),
                )
            )
        )


def _meta(implementation: str, implementation_version: str) -> cucumber.Meta:
    """Who produced the stream, and against which protocol version."""
    return cucumber.Meta(
        cpu=cucumber.Product(name=platform.machine() or _UNKNOWN_VERSION),
        implementation=cucumber.Product(
            name=implementation, version=implementation_version
        ),
        os=cucumber.Product(name=platform.system() or _UNKNOWN_VERSION),
        protocol_version=_protocol_version(),
        runtime=cucumber.Product(
            name=platform.python_implementation(), version=platform.python_version()
        ),
    )


def messages_protocol_version() -> str:
    """The Messages release this stream was produced against.

    Exposed because the report envelope has to record it too. Messages is
    versioned and the implementations pin different releases -- this one is on
    34.2.0 while the Go TCK builds against v21 -- so a consumer holding two
    reports cannot assume one schema validates both. Sharing this one function
    with the stream's own Meta message means the envelope and the stream cannot
    disagree about which release produced it.
    """
    return _protocol_version()


def _protocol_version() -> str:
    """The Messages version this stream is written against.

    Read from the installed library rather than written down, because the library
    is what decides: a version pinned here would go on claiming 34.2.0 after a
    dependency bump moved the types underneath it.
    """
    try:
        return importlib.metadata.version(_MESSAGES_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        return _UNKNOWN_VERSION


def _envelope(envelope: cucumber.Envelope) -> dict[str, typing.Any]:
    converted: dict[str, typing.Any] = cucumber.message_converter.to_dict(envelope)
    return converted


def _timestamp(nanoseconds: int) -> cucumber.Timestamp:
    return cucumber.Timestamp(
        seconds=nanoseconds // 1_000_000_000, nanos=nanoseconds % 1_000_000_000
    )


def _duration(nanoseconds: int) -> cucumber.Duration:
    nanoseconds = max(nanoseconds, 0)
    return cucumber.Duration(
        seconds=nanoseconds // 1_000_000_000, nanos=nanoseconds % 1_000_000_000
    )


def feature_uri(relative_filename: str) -> str:
    """Normalise pytest-bdd's relative feature path into a Cucumber uri.

    pytest-bdd builds it with ``os.path.join``, so on Windows it arrives
    backslash-separated. A uri is slash-separated everywhere, and the same string
    has to appear in the ``Source``, the ``GherkinDocument`` and every ``Pickle``
    or nothing ties them together -- so a report emitted on Windows would
    otherwise not be comparable with one emitted on Linux.
    """
    return PurePath(relative_filename).as_posix()
