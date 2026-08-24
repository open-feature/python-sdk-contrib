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
    features_path,
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


scenarios(features_path())
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
| `Capability.TARGETING` | `@targeting` | reserved; no scenarios yet |
| `Capability.CACHING` | `@caching` | reserved; no scenarios yet |

`@lifecycle` and `@events` are deliberately separate, and the split matters in both directions. An
SDK dispatches `PROVIDER_READY` around `initialize` for *any* provider, so a provider declaring only
`@events` passes the readiness scenario without demonstrating anything — a `NoOpProvider` passes it
identically. Meanwhile a stateless provider has a real initialisation to verify but no event stream
of its own to declare `@events` for, and gating on `@events` shut it out of a scenario it should be
held to.

Untagged scenarios are mandatory and always run. `capabilities` defaults to everything — narrow it
rather than widening it: start from the default, run the suite, and remove only what your provider
genuinely cannot do.

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

The self-test marks that one row `xfail(strict=True)` with a pointer to the issue, so it stays
visible in the report and un-hides itself automatically once the SDK is fixed.

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

Set `PROVIDER_TCK_REPORT_DIR` and each suite writes a machine-readable record of its run to
`<dir>/<name>.json`, conforming to the [report schema][report-schema] in the specification.

```console
$ PROVIDER_TCK_REPORT_DIR=./reports pytest
provider-tck [in-memory]: report written to reports/in-memory.json (1 failed, 5 not-declared, 23 passed)

$ jq '.scenarios | group_by(.outcome) | map({(.[0].outcome): length}) | add' reports/in-memory.json
{
  "failed": 1,
  "not-declared": 5,
  "passed": 23
}
```

It is an environment variable rather than a `TckConfig` field so that emitting a report is a property
of the *run* and not of the code: CI sets it, a developer running the suite locally does not, and no
adopter changes a line to publish one. Unset means no report, which is not an error. Several suites
in one pytest session each write their own file, so flagd's two resolvers would not collide.

### Why every scenario is listed

Appendix F requires that a scenario skipped for an undeclared capability is reported as skipped
**with the reason** and never as passed. A consumer cannot check that against a summary line, so the
report records the outcome of *every* scenario individually — and is required to be complete, because
a document that quietly dropped what it skipped would satisfy the letter of the rule and still
mislead whoever read it.

Which also means the report is not a transcription of pytest's summary. The run above finishes green:
the one scenario the Python SDK cannot satisfy is marked `xfail` (finding 1), so pytest counts it as
expected and exits zero. The provider still did not satisfy it, and the document says `failed` with
the reason — an expected failure is a recorded deviation, not an excused one.

Four outcomes rather than two, because "did not run" is not one thing:

| Outcome | Means |
| --- | --- |
| `passed` | the scenario ran and passed |
| `failed` | the scenario ran and failed, including a known deviation marked `xfail` |
| `not-declared` | skipped because the provider did not declare a capability the scenario is tagged with |
| `not-applicable` | skipped for any other reason — a marker an adopter applied, a step calling `pytest.skip` |

### What identifies a report

`tck.specRevision` and `tck.assetsTree` come from `spec_revision.json`, which `hatch_build_sync.py`
generates from the submodule alongside the copied assets. It has to be captured at build time: the
submodule is not in the wheel, so an installed copy has nothing left to ask. A build that cannot
reach git — an unpacked sdist, say — warns and records `unknown` rather than inventing a commit.

The tree hash is carried as well as the commit because it identifies the assets alone. It is
unchanged by unrelated edits elsewhere in the specification, so two runs that executed identical
assets report the same value even when pinned to different commits — and it is checkable, since
`git rev-parse <specRevision>:specification/assets/provider-tck` must reproduce it.

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
| `test_report` | the conformance report | checks the two properties a consumer is entitled to assume |

```
78 passed, 9 skipped, 2 xfailed
```

No Docker and no network. The conformance suites take under a second; `test_report` takes most of a
minute, because the properties it checks are properties of a whole pytest session and it runs four of
them in subprocesses to check them.

Neither in-memory suite declares `@lifecycle`, so the three lifecycle scenarios are skipped in both.
That is the point: with no backend to reach, they would pass without testing anything — which is
what they did while the feature was gated on `@events`.

## Known gaps

- **Evaluation context passthrough is unverifiable.** The scenarios build evaluation contexts but
  cannot assert one *reached* the backend. That needs an echo operation on the control API.
- **No HTTP control client yet.** It arrives with the first containerised adopter.
- **Caching, hooks and flag metadata** are not covered.
- **A report cannot name a Scenario Outline row portably.** Every row of an outline shares one
  scenario name, and the report schema has nowhere to put the row, so several entries would be
  indistinguishable — including, here, one that differs in outcome from its siblings. This
  implementation qualifies the name with pytest's example id (`... [boolean-flag-Integer-1]`), which
  is unambiguous but is not what another language would produce for the same row. Raised on
  [open-feature/spec#424](https://github.com/open-feature/spec/issues/424).

[report-schema]: https://github.com/open-feature/spec/blob/main/specification/assets/provider-tck/report/conformance-report.schema.json
[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
