# OpenFeature Provider TCK (Python)

A conformance suite any OpenFeature Python provider can adopt to verify that it implements the
provider contract of the specification.

OpenFeature's central promise is that swapping providers does not change application behaviour.
Nothing verifies that today, and every provider tests differently — so "implements the provider
contract" is an unverified claim, and a behavioural difference between two providers is discovered
by the application that trips over it.

This package is the Python implementation of [Appendix F][appendix-f]. It runs the same Gherkin
scenarios, against the same canonical flag set, driven through the same backend control API, as
every other language's TCK. That shared basis is the point: "conformant" only means something if the
question is identical everywhere.

Tracking issue: [open-feature/spec#417][tracking].

## Status

**Proof of concept.** The scenario set is a representative subset covering each architectural
mechanism once, not exhaustive coverage. Breaking changes should be expected.

## Adopting it

One fixture and one call. It uses **pytest-bdd**, the same runner the flagd provider and the flagd
testkit already use, so an adopting package gains no new test framework.

```python
import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.provider_tck import (
    Capability,
    TckConfig,
    feature_paths,
)


@pytest.fixture(scope="session")
def tck_config():
    control = MyBackendControl()
    return TckConfig(
        name="my-provider",
        control=control,
        new_provider=lambda: MyProvider(control.address),
        capabilities={Capability.EVENTS, Capability.OBJECT},
    )


scenarios(*feature_paths())
```

There is **no `conftest.py` to write and nothing to import for the steps**. The step definitions
arrive through this package's pytest plugin, registered via a `pytest11` entry point, so installing
the package is all it takes.

The TCK owns the whole lifecycle: registering the provider under a suite-scoped domain, awaiting
events, resetting the backend between scenarios, releasing it at the end. **If you find yourself
writing test infrastructure, that is a defect here rather than something for you to work around.**

pytest-bdd generates one test per scenario — and one per row of a Scenario Outline — so failures
name a scenario and `-k` selects one as usual. The feature files and canonical flag set are packaged
inside the distribution, so **adopting this package needs no git submodule** — see
[Where the assets come from](#where-the-assets-come-from).

### Timings

`TckConfig.event_timeout` is the knob that matters. Providers observe backend changes on wildly
different timescales — a streaming provider sees a configuration change in milliseconds, one that
polls every 30 seconds may need most of a poll interval. Set it to comfortably exceed your
worst-case detection latency, or the suite reports timeouts that are really just impatience.

## Adding your own scenarios

A provider is rarely only a provider. flagd has `fractional` targeting, another vendor has a
proprietary rollout rule, and the behaviour of those is as worth pinning as the contract they sit on
top of. Verifying them used to mean a second harness: a second backend lifecycle, a second set of
fixtures, a second thing to keep working.

Put them in the same run instead. Create a directory named `tck-extensions` beside the module that
calls `scenarios()`, and write step definitions for whatever is new in a `conftest.py` beside it:

```
tests/
├── conftest.py                    # your step definitions
├── test_conformance.py            # the fixture and the one call, unchanged
└── tck-extensions/
    └── fractional.feature
```

```python
# conftest.py
from pytest_bdd import then

from openfeature.contrib.tools.provider_tck import TckState


@then("the fractional rule splits the population")
def fractional_splits(tck_state: TckState) -> None:
    ...
```

That is the whole of it — **no registration, no option and no new argument**. pytest collects
`conftest.py` on its own, pytest-bdd resolves steps through the fixture system, and the canonical
step vocabulary is in scope in your feature file beside your own steps. `tck_state` is the same
per-scenario state the canonical steps use, so your scenario runs against the provider the suite
registered, in the same backend lifecycle, with the same reset between scenarios.

The one thing pytest cannot find by itself is the feature files, because the canonical ones are
inside the installed distribution rather than in your repository. `feature_paths()` returns both:

```python
scenarios(*feature_paths())
```

That line does not change when you add an extension, and it is the only difference from the older
`scenarios(features_path())` — which still works and still sees only the canonical set. An adopter
with no `tck-extensions` directory runs exactly what they ran before: same scenarios, same count,
same report.

### Your scenarios cannot stand in for ours

In the report, canonical scenarios are the ones under the `features/` uri prefix and yours are under
`extensions/` — the prefix Go and JavaScript mount theirs under too, so a consumer holding reports
from several languages applies one rule. The prefix is derived from where a file *is*, not from what
the runner called it, and two cases are refused outright rather than documented:

- **A feature file of yours under the reserved `features/` prefix.** Handing `scenarios()` a
  directory of your own named `features` is the one route left to a canonical-looking uri. No report
  is written and the run fails.
- **Two feature files that would share one uri.** A Cucumber Messages stream carries one source per
  uri, so the second file's scenarios would be reported against the first file's source.

This is not hypothetical. Java's suite found that a same-named feature file in a second classpath
root *replaced* the canonical one, and the run went green having asked the adopter's questions
instead of the specification's — the worst outcome available to a conformance suite. The Python
route to the same place is narrower and just as quiet: pytest-bdd names a feature file by its parent
directory joined to its own name, so `tck-extensions/features/errors.feature` arrives under the uri
the canonical `errors.feature` already occupies.

## Capabilities

Not every provider implements every optional part of the contract. Each scenario exercising an
optional part carries a Gherkin tag, pytest-bdd turns that tag into a pytest marker, and a provider
declares what it supports.

**A scenario whose capability was not declared is reported as skipped, with the reason — never as
passed.** A conformance suite that quietly goes green on scenarios it did not run is worse than no
suite at all, so `pytest.skip` carries the reason into the report:

```
SKIPPED provider does not declare capability @stale.
        Declared: @events @numeric-coercion @object
```

| Capability | Tag | Meaning |
| --- | --- | --- |
| `Capability.LIFECYCLE` | `@lifecycle` | reaches its backend during initialisation, observably and promptly |
| `Capability.EVENTS` | `@events` | emits lifecycle events at all |
| `Capability.STALE` | `@stale` | enters `STALE` and emits `PROVIDER_STALE` on backend loss |
| `Capability.CONFIGURATION_CHANGE` | `@configuration-change` | detects configuration changes and emits `PROVIDER_CONFIGURATION_CHANGED` |
| `Capability.OBJECT` | `@object` | supports structured flag values |
| `Capability.UNAVAILABLE_INIT` | `@unavailable` | reports an error state instead of hanging against a dead backend |
| `Capability.NUMERIC_COERCION` | `@numeric-coercion` | coerces between integer and float only when lossless, else `TYPE_MISMATCH` |
| `Capability.TARGETING` | `@targeting` | reserved; **not declarable** — no scenarios yet |
| `Capability.CACHING` | `@caching` | reserved; **not declarable** — no scenarios yet |

`@lifecycle` and `@events` are deliberately separate, and the split matters in both directions. An
SDK dispatches `PROVIDER_READY` around `initialize` for *any* provider, so a provider declaring only
`@events` passes the readiness scenario without demonstrating anything — a `NoOpProvider` passes it
identically. Meanwhile a stateless provider has a real initialisation to verify but no event stream
of its own to declare `@events` for, and gating on `@events` shut it out of a scenario it should be
held to.

Untagged scenarios are mandatory and always run. `capabilities` defaults to every *declarable*
capability — `DECLARABLE_CAPABILITIES` — and you should narrow it rather than widen it: start from
the default, run the suite, and remove only what your provider genuinely cannot do.

A reserved capability is documented so the vocabulary has a place for it once scenarios exist, and
until then it **must not be declared**. Nothing carries the tag, so declaring it cannot be verified,
cannot produce a skip, and tells a reader of a conformance report only that something was claimed and
nothing examined. `TckConfig` raises if you name one in `capabilities` or in `not_applicable`, and
`DECLARABLE_CAPABILITIES` excludes them — which is the case that matters, because "every capability
except X" is how a reserved tag reaches a report by accident rather than by decision. One
implementation's published report asserts `@targeting` and `@caching` as declared for exactly that
reason.

`@numeric-coercion` deserves a note, because it is the one capability here that **the specification
does not define**. OpenFeature has a single numeric type on purpose — `number` is "a numeric value of
unspecified type or size", and languages **may** differentiate between integers and floats "as idioms
dictate" — so no requirement says what a provider must do when a value does not fit the accessor it
was asked through. That gap is [open-feature/spec#430](https://github.com/open-feature/spec/issues/430).

The rule this tag is tested against is therefore **borrowed, not normative**: lossless coercion is
permitted, lossy coercion must fail — `10.0` requested as an integer must succeed, `0.5` must not.
It comes from flagd's
[numeric coercion ADR](https://github.com/open-feature/flagd/blob/main/docs/architecture-decisions/numeric-coercion.md),
which is scoped to flagd's own implementations, and the tag carries that name — it was
`@strict-numeric-typing` — because two vocabularies for one observable property is worse than one
borrowed name. **A provider that behaves differently is not violating the specification**, so
withholding this capability may be a deliberate choice as readily as a defect.

Only the lossy half is tested. The canonical flag set has no integral float to ask the lossless half
of, so a provider that wrongly rejects `10.0` as an integer still passes; adding one changes the flag
set for every language at once. Appendix F records that as an open gap, together with a second one:
the width of a language's integer accessor — 64-bit against 32-bit — is not modelled at all.

For a capability that *cannot* hold rather than one you chose not to declare, use
`not_applicable={Capability.X: "why"}`. The suite treats it identically — the scenarios are skipped
either way — but the report keeps the two apart, because collapsing them misrepresents a provider:
declining an optional feature is a choice, and an impossibility is not.

## Controlling the backend

`BackendControl` is the single seam between the scenarios and whatever manipulates the backend. Step
definitions never talk to a backend directly, which is why the same Gherkin runs unchanged against a
containerised backend and against a provider manipulated in-process.

**If your provider talks to a backend, drive it over the HTTP control API** — the document is
available as `control_api_spec()`. That API is the normative contract for those providers, and it is
what makes a conformance claim portable: another language's TCK drives the same endpoints against
the same stack and must get the same answers.

Two of its requirements are easy to get wrong:

- **Containers are never stopped or restarted mid-suite.** Unavailability is simulated *inside* the
  running stack. Container orchestrators assign host ports dynamically and cannot reliably preserve
  them across a restart, so restarting silently invalidates every provider already pointed at the
  old port, and the failure looks like a flaky provider.
- **`/start` resets flag state; `/restart` preserves it.** An outage must be observable as a change
  in availability, never as a change in flag values.

### Providers with no backend

An in-memory, environment-variable or file-based provider has nothing to connect to. Those may
control the backend in-process, where flag operations are direct manipulations of the provider's own
state. `InProcessControl` is the reference.

This is a narrow allowance and the obvious thing to abuse. **A provider with an external backend
must use the control API.** Reaching into an external backend from inside the test process — a
test-only admin client, a shared database handle, a hook inside the provider — produces a suite that
passes while proving nothing, because the path it exercised is not the path the contract describes.

Connection-dependent scenarios have no meaning without a connection, so a backend-less control
simply does not implement `ConnectionControl`, leaves `STALE` and `UNAVAILABLE_INIT` undeclared, and
those scenarios are skipped with their reason.

## Findings

Two, both confirmed by running the suite rather than by reading code.

### 1. A boolean satisfies an Integer request

`boolean-flag` evaluated through `get_integer_details` returns `True` with reason `STATIC` and **no
error code**, where the specification requires the code default and `TYPE_MISMATCH`. The client
type-checks with `isinstance(value, int)`, and `bool` is a subclass of `int` in Python.

This is **Python-specific** — the identical scenario passes in every other language's suite, which
is a fair advertisement for having more than one implementation. Tracked as
[open-feature/python-sdk#619](https://github.com/open-feature/python-sdk/issues/619).

The self-test marks that one row `xfail(strict=True)` with a pointer to the issue, so the run
un-hides itself automatically once the SDK is fixed, and declares it in
`TckConfig.known_deviations`, so the report acknowledges it. The results payload still reports the
scenario as `FAILED`: the acknowledgement records the gap, it does not soften it.

### 2. The in-memory provider cannot update its flag set

[Appendix A][appendix-a] requires an SDK's in-memory provider to support updating the flag set and
emitting `PROVIDER_CONFIGURATION_CHANGED`. Python's copies its mapping in the constructor and
exposes nothing to change it. Tracked as
[open-feature/python-sdk#620](https://github.com/open-feature/python-sdk/issues/620).

Only half the machinery is missing — `AbstractProvider` already supplies
`emit_provider_configuration_changed` — which is why `ControllableInMemoryProvider` here is a small
subclass rather than a reimplementation, and why it should port back to the SDK as a method.

## Where the assets come from

The Gherkin feature files, the canonical flag set and the control-API document are **not owned by
this repository**. They are the language-agnostic conformance artifacts defined in
[open-feature/spec][spec] under `specification/assets/provider-tck/`, and every language's TCK ships
the same ones — which is the only reason a conformance claim means the same thing in Python as it
does in Java.

**Adopting this package needs no submodule.** The assets are copied into the wheel and the sdist at
build time, so `pip install openfeature-provider-tck` gives you everything the suite runs on.

**Contributing to this package does.** The spec is a git submodule at
`tools/openfeature-provider-tck/spec`, and the copies under
`src/openfeature/contrib/tools/provider_tck/` are gitignored and generated:

```bash
git submodule update --init tools/openfeature-provider-tck/spec
poe test   # runs `poe sync-spec-assets` first
```

The copies carry a `DO-NOT-EDIT.txt` because editing them forks the definition of conformance, which
is the one thing this suite exists to prevent. A change goes to [open-feature/spec][spec] first;
then bump the submodule pin here. Committing no copies means the spec revision this package targets
is recorded by the pin and nowhere else, so the two cannot drift apart unnoticed.

This mirrors what `openfeature-flagd-api-testkit` already does for the flagd test harness.

## Conformance reports

Set `PROVIDER_TCK_REPORT_DIR` and each suite writes **two** files: an envelope at `<dir>/<name>.json`,
conforming to the [report schema][report-schema] in the specification, and the results it points at
at `<dir>/<name>.ndjson`, which is a [Cucumber Messages][messages] stream.

```console
$ PROVIDER_TCK_REPORT_DIR=./reports pytest
provider-tck [in-memory]: report written to reports/in-memory.json with results in in-memory.ndjson (1 failed, 23 passed, 5 skipped)

$ jq -c .results reports/in-memory.json
{"format":"cucumber-messages","location":"in-memory.ndjson","digest":"sha256:c7e12a…"}

$ jq -r 'select(.testStepFinished) | .testStepFinished.testStepResult.status' \
    reports/in-memory.ndjson | sort | uniq -c
      1 FAILED
    220 PASSED
     45 SKIPPED
```

Statuses are per step, not per scenario. Of the 45 skipped, 42 belong to the five scenarios the
capability gate stopped — their before-hooks included, which is where the reason is — and three are
the steps of the failing scenario that were never reached.

It is an environment variable rather than a `TckConfig` field so that emitting a report is a property
of the *run* and not of the code: CI sets it, a developer running the suite locally does not, and no
adopter changes a line to publish one. Unset means no report, which is not an error. Several suites
in one pytest session each write their own pair, so flagd's two resolvers would not collide.

### A partial run is not a conformance run

The canonical scenario set is fixed by the specification, and a run that executed less of it cannot
support a conformance claim. `-k`, `-m`, `--deselect`, or a test module that stopped calling
`scenarios()` on the canonical path each run fewer scenarios, and none of them is an error to
pytest. Go measured the consequence: `-run` on a single scenario passed green and emitted a
well-formed report covering 1 of 29 canonical scenarios, with nothing in the document saying so.

So every run is checked against the scenarios this distribution ships, and a suite that did not
execute all of them writes no report:

```console
$ PROVIDER_TCK_REPORT_DIR=./reports pytest -k "unknown_flag_key"
provider-tck [in-memory]: 28 of 29 canonical scenarios did not run, so this run cannot support a
conformance claim and no report is written for it. …
  - features/errors.feature: A float flag is not silently narrowed to an integer
  - features/errors.feature: Requesting the wrong type returns the code default [key=float-flag requested=Boolean default=false]
  … and 18 more
```

A scenario the capability gate skipped **has** run: it was asked, and the report accounts for it
with its reason, so declining a capability never trips this. Your own scenarios are yours — they are
not counted towards the canonical set and cannot close a gap in it.

Set `PROVIDER_TCK_PARTIAL=1` to work on a single scenario without the guard failing the run. It buys
a green run and nothing else: no report is written for an incomplete suite either way. Java's TCK
spells the same escape hatch the same way.

### Why the results are not our format

Per-scenario outcomes, tags, Scenario Outline row identity and the executed feature source are all
already specified by Cucumber Messages, which is maintained, cross-language, schema'd, and emitted
natively by cucumber-jvm. Defining them again in the report schema created a second format to
maintain and version, and two places for the same fact to disagree. So the envelope says what was
tested and what the provider claims; the payload says what happened.

The results are referenced rather than inlined because the stream carries the feature sources and is
far larger than the envelope, and a consumer deciding whether it cares about a report should not have
to fetch a whole run to find out. `results.digest` is a SHA-256 over the exact bytes written, so a
consumer can tell that what it fetched is what the envelope described.

Two things Messages cannot carry, so they stay in the envelope. `declaration` is an *input* to
reading the results rather than a summary of them: a skipped scenario says the question was not put
to this provider, and only the declaration says whether that is because the provider declines the
capability. And no standard results format has a slot for the tested subject — Messages records the
runtime and the OS, not what was being asked about.

### Reading the payload

Appendix F requires that a scenario skipped for an undeclared capability is reported as skipped
**with the reason** and never as passed. A consumer cannot check that against a summary line, so the
stream carries every scenario the run collected, including the ones the capability gate skipped
before their first step, and Cucumber's own `SKIPPED` is what it reports them as.

Each scenario is a `TestCase` referring to a `Pickle`, and a test case is as bad as its worst step,
which is Cucumber's rule. Every test case carries two hook steps as well as its Gherkin steps: pytest
runs a scenario in three phases and only the middle one executes steps, so the before-hook is where a
capability skip's reason lands and the after-hook is where a teardown failure does.

Given a scenario's tags — in its pickle — and the envelope's `declaration`, the capability
responsible for a skip follows, which is why it is no longer transported once per scenario.

Which also means the payload is not a transcription of pytest's summary. The run above finishes
green: the one scenario the Python SDK cannot satisfy is marked `xfail` (finding 1), so pytest counts
it as expected and exits zero. The provider still did not satisfy it, and the stream says `FAILED`.
The acknowledgement goes in the envelope's `knownDeviations` instead — an expected failure is a
recorded deviation, not an excused one — which an adoption declares with `TckConfig.known_deviations`.

### Which row of a Scenario Outline

A pickle's `astNodeIds` are `[scenario id, table row id]`, and the row id resolves in the
`GherkinDocument` to exactly the cells the feature file wrote. That is what tells the eleven rows of
the type-mismatch matrix apart — one of which differs in outcome from its ten siblings — and it is
exact rather than a naming convention every implementation has to reproduce byte-for-byte.

### What identifies a report

`tck.specRevision` comes from `spec_revision.json`, which `hatch_build_sync.py` generates from the
submodule alongside the copied assets. It has to be captured at build time: the submodule is not in
the wheel, so an installed copy has nothing left to ask. A build that cannot reach git — an unpacked
sdist, say — warns and records `unknown` rather than inventing a commit.

No asset tree hash. It was carried so a consumer could tell whether two runs executed the same
questions; the payload's `Source` messages carry the executed feature files verbatim, which answers
that directly rather than by proxy.

`provider.name` is what the provider reports through its own metadata, not `TckConfig.name`.
`TckConfig.name` is chosen to read well in a failure message — `flagd-rpc` — which makes it the
*configuration*, and it is reported as such. One provider with two materially different modes
produces two reports that are not interchangeable.

`backend.controlApi` is read off an optional `control_api` property on your `BackendControl`,
returning `"http"` or `"in-process"`. It is not a member of the protocol: adding one would make every
existing control incomplete for the sake of one string, and a control that stays quiet simply omits
the field.

## The self-tests

| Suite | Subject | Why |
| --- | --- | --- |
| `test_in_memory_conformance` | the SDK's `InMemoryProvider` | reference adoption for a backend-less provider |
| `test_controllable_conformance` | `ControllableInMemoryProvider` | the only suite that exercises the configuration-change path — see finding 2 |
| `test_in_process_control` | `InProcessControl` | pins what the Gherkin cannot assert about itself |
| `test_report` | the conformance report | checks the two properties a consumer is entitled to assume, against the emitted Messages stream |
| `test_extensions` | an adopter's own scenarios | an extension runs inside the canonical suite, changes nothing for an adopter who has none, and cannot stand in for a canonical scenario |
| `test_canonical_set` | the canonical-set guard | a run that executed less than the canonical set fails and publishes nothing |

```
132 passed, 9 skipped, 2 xfailed
```

No Docker and no network. The conformance suites take under a second; `test_report`,
`test_extensions` and `test_canonical_set` take most of the time, because the properties they check
are properties of a whole pytest session and they run generated adoptions in subprocesses to check
them.

Neither in-memory suite declares `@lifecycle`, so the three lifecycle scenarios are skipped in both.
That is the point: with no backend to reach, they would pass without testing anything — which is
what they did while the feature was gated on `@events`.

## Known gaps

- **Evaluation context passthrough is unverifiable.** The scenarios build evaluation contexts but
  cannot assert one *reached* the backend. That needs an echo operation on the control API.
- **No HTTP control client yet.** It arrives with the first containerised adopter.
- **Caching, hooks and flag metadata** are not covered.
- **The results payload is assembled here.** pytest-bdd emits no Cucumber Messages — it ships the
  legacy Cucumber JSON format and nothing for the ndjson protocol — so `messages.py` builds the
  stream from the official types and re-parses the feature files to get the AST node ids a pickle
  refers to. If pytest-bdd ever emits Messages itself, that module should shrink to a shim. Whether
  a report belongs inside a provider's released artifact is still open on
  [open-feature/spec#424](https://github.com/open-feature/spec/issues/424).

[report-schema]: https://github.com/open-feature/spec/blob/main/specification/assets/provider-tck/report/conformance-report.schema.json
[messages]: https://github.com/cucumber/messages
[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
