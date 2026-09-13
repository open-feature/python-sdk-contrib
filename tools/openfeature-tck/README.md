# OpenFeature TCK (Python)

A conformance suite any OpenFeature Python provider can adopt to check that it implements the
provider contract of the specification.

It is the Python implementation of [Appendix F][appendix-f], which defines the Gherkin scenarios, the
canonical flag set and the control API every language's TCK runs, and carries the reasoning behind
all of it. **This README documents the Python binding and nothing else**; where a question is not
Python's, it links there.

Tracking issue: [open-feature/spec#417][tracking]. **Status: proof of concept**, so expect breaking
changes. The one known gap that is this package's rather than the suite's: no multi-provider suite,
because the Python SDK has no multi-provider.

## Quick start

Two fixtures and one call.

```bash
pip install 'openfeature-tck[compose]'
```

```python
import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.tck import (
    Capability,
    ComposeBackend,
    RunningBackend,
    TckConfig,
    feature_paths,
)


@pytest.fixture(scope="session")
def compose_backend():
    return ComposeBackend(
        compose_file="tests/tck/docker-compose.yaml",
        backend_ports=[8013],
    )


@pytest.fixture(scope="session")
def tck_config(tck_backend: RunningBackend):
    return TckConfig(
        name="my-provider",
        control=tck_backend.control,
        new_provider=lambda: MyProvider(
            host=tck_backend.endpoint.host,
            port=tck_backend.endpoint.port(8013),
        ),
        capabilities={Capability.EVENTS, Capability.OBJECT},
    )


scenarios(*feature_paths())
```

That is the whole adoption. **There is no `conftest.py` to write and nothing to import for the
steps** — they arrive through this package's pytest plugin, registered via a `pytest11` entry point —
and the assets ship in the distribution, so **adopting needs no git submodule**. The runner is
**pytest-bdd**, which the flagd provider and testkit already use, so an adopting package gains no new
test framework, and one test is generated per scenario and per Scenario Outline row.

The suite owns the container stack and the provider lifecycle: starting Compose, discovering the
mapped host ports, building the HTTP control, registering the provider, awaiting events, resetting
the backend between scenarios, tearing down. **If you find yourself writing test infrastructure,
that is a defect here rather than something for you to work around.**

### A provider with no backend

An in-memory, environment-variable or file-based provider supplies a `BackendControl` of its own,
where flag operations are direct manipulations of the provider's state. No Compose file and no
container tooling: `testcontainers` is the optional `compose` extra, imported lazily.

```python
@pytest.fixture(scope="session")
def tck_config():
    control = InProcessControl()
    return TckConfig(
        name="my-provider",
        control=control,
        new_provider=control.new_provider,
        capabilities={Capability.EVENTS, Capability.OBJECT},
    )
```

It is a narrow allowance — **a provider with an external backend must drive it over the HTTP control
API**, for which `HttpControl` is the client, built on `urllib.request` alone so the TCK gains no
HTTP dependency; `control_api_spec()` returns the document a backend under test implements. Every
control states which path it took: `control_api` is a **required** member of `BackendControl`, typed
`Literal["http", "in-process"]`, with no default and no inference from the concrete type. A
backend-less one does not implement `ConnectionControl`, so `STALE` and `UNAVAILABLE_INIT` go
undeclared and their scenarios skip.

## The options

### `TckConfig`

| field | required | default | meaning |
| --- | --- | --- | --- |
| `name` | yes | — | the provider's name, as it appears in a report |
| `control` | yes | — | the `BackendControl` the scenarios drive the backend through |
| `new_provider` | yes | — | builds the provider under test, configured but uninitialised. Called **once per scenario**, because the mapped ports do not exist until the stack is up |
| `new_unavailable_provider` | no | `None` | builds a provider pointed at a closed port, for the initialisation-failure scenarios. Needed only if `capabilities` includes `UNAVAILABLE_INIT`; give it a short connection deadline, since the scenario allows a bounded time for the error |
| `capabilities` | no | `DECLARABLE_CAPABILITIES` | which optional parts of the contract this provider supports |
| `known_deviations` | no | `()` | gaps the provider is known to have |
| `event_timeout` | no | `12.0` | seconds to wait for a provider event |
| `ready_timeout` | no | `30.0` | seconds to wait for `READY`, and the longest a direct `shutdown`/`initialize` is given before the wait is recorded as a failure |

`event_timeout` is the knob that matters: set it comfortably above your provider's worst-case
detection latency — a poller may need most of a poll interval — or the suite reports timeouts that
are really just impatience.

### `ComposeBackend`

| field | required | default | meaning |
| --- | --- | --- | --- |
| `compose_file` | yes | — | path to the Compose file, resolved relative to the package directory |
| `backend_ports` | yes | — | container-internal ports the **provider** connects to. The control port is exposed automatically and must not be listed here |
| `backend_service` | no | `"backend"` | the Compose service hosting both the control API and the backend |
| `control_port` | no | `8080` | container-internal port of the control API |
| `additional_ports` | no | `{}` | extra service to ports, for a stack with more than one service. Resolved through the endpoint by service name |
| `backend_configuration` | no | `"default"` | the configuration name passed to `POST /start` |
| `startup_timeout` | no | `60.0` | seconds to wait for the stack and its control API to become reachable |

These names and defaults are fixed across all four languages' TCKs, so a provider shipped in two of
them writes one Compose file and two declarations against it.

`tck_backend` is a session-scoped fixture the plugin builds from your `compose_backend` fixture,
yielding `.control` — the `HttpControl`, already awaited ready, and one per stack, since it remembers
whether a disconnect left the backend down — and `.endpoint`, with `host`, `port(internal)` and
`port(internal, service=...)`. Your Compose file must **not pin host ports**; declaring
`backend_ports` is what lets the harness say "the Compose file does not publish 8013" at startup
rather than three scenarios later. For a different fixture name or scope:

```python
@pytest.fixture(scope="session")
def tck_backend():
    yield from run_compose_backend(ComposeBackend(...))
```

## Declaring capabilities

Each scenario exercising an optional part of the contract carries a Gherkin tag, pytest-bdd turns it
into a marker, and a provider declares what it supports. **An undeclared capability's scenarios are
reported as skipped with the reason — never as passed:**

```
SKIPPED provider does not declare capability @stale.
        Declared: @events @large-integers @object @variants
```

| Capability | Tag | Meaning |
| --- | --- | --- |
| `Capability.LIFECYCLE` | `@lifecycle` | reaches its backend during initialisation, observably |
| `Capability.EVENTS` | `@events` | emits lifecycle events at all |
| `Capability.STALE` | `@stale` | enters `STALE` and emits `PROVIDER_STALE` on backend loss |
| `Capability.CONFIGURATION_CHANGE` | `@configuration-change` | emits `PROVIDER_CONFIGURATION_CHANGED` on a configuration change |
| `Capability.OBJECT` | `@object` | supports structured flag values |
| `Capability.VARIANTS` | `@variants` | names the variant it resolved |
| `Capability.DISABLED_FLAGS` | `@disabled-flags` | resolves a disabled flag to the code default |
| `Capability.UNAVAILABLE_INIT` | `@unavailable` | errors rather than hangs against a dead backend |
| `Capability.NUMERIC_COERCION` | `@numeric-coercion` | coerces int/float only when lossless, else `TYPE_MISMATCH` |
| `Capability.STRING_TYPING` | `@string-typing` | reports `TYPE_MISMATCH` for a non-string flag asked for as a string |
| `Capability.LARGE_INTEGERS` | `@large-integers` | resolves integers up to 2^53 − 1 exactly |
| `Capability.REINITIALIZATION` | `@reinitialization` | can be initialised again after `shutdown` |
| `Capability.TARGETING` | `@targeting` | resolves differently for a matching evaluation context |
| `Capability.STANDARD_REASONS` | `@standard-reasons` | uses the standard resolution reasons with their standard meanings |
| `Capability.CACHING` | `@caching` | reserved; **not declarable** — no scenarios yet |

Untagged scenarios are mandatory and always run. `capabilities` defaults to
`DECLARABLE_CAPABILITIES`; narrow it rather than widen it. Tags compose, so declaring
`@reinitialization` without the `@lifecycle` its feature carries leaves that scenario skipped.
**What counts as "cannot do" is [Appendix F][appendix-f]'s rules for declaring**; the adoptions here
cite them rather than restating them, and so should yours.

`TckConfig` refuses two declarations at construction rather than letting them reach a report: a
**reserved** capability, which no scenario carries, and one this language's SDK **cannot express** —
the two errors and the two skip reasons deliberately differ, and a scenario arriving with a reserved
tag fails the run. `INEXPRESSIBLE_CAPABILITIES` is **empty in Python**, measured rather than assumed:
`int` is arbitrary-precision and the integer and float accessors reach separate provider methods, so
both tags are ordinary declarable capabilities here.

### Known deviations

`known_deviations` says what a capability set cannot: that the provider fails something it is
**required** to do. It is a declaration, not a switch — the scenario still runs and still fails.

```python
TckConfig(
    # ...
    known_deviations=(
        KnownDeviation.tracked(
            summary="what is wrong, for someone comparing providers",
            issue="https://github.com/open-feature/flagd/issues/1996",
            capability=Capability.NUMERIC_COERCION,
        ),
    ),
)
```

`summary` is required; `issue` is optional, with `KnownDeviation.untracked(summary=...)` for a gap
tracked nowhere yet; `capability` is optional, left out for a mandatory ungated scenario, and a
reserved one is refused since no scenario carries the tag. [Appendix F][appendix-f] settles which of
the two shapes — declare and let it fail, or withhold and let it skip — to reach for.

## Running it

**Keep the adoption suite out of the default build, give it a task of its own, and write down that
you did** — the reasoning is Appendix F's ["Running the suite in CI"][appendix-f]. The Python part is
these tasks, which CI reaches through `poe cov`:

```toml
[tool.poe.tasks]
test = { sequence = ["test-default", "test-tck-collect"], ignore_fail = "return_non_zero" }
test-cov = { sequence = ["test-cov-default", "test-tck-collect"], ignore_fail = "return_non_zero" }
test-default = "pytest tests --ignore=tests/tck"
test-cov-default = "coverage run -m pytest tests --ignore=tests/tck"
test-tck = "pytest tests/tck"
test-tck-collect = "pytest tests/tck --collect-only -q"
```

Put a comment above them saying why, so the exclusion cannot read as an oversight, and record the
current tally where a reviewer will see it — **read the tally rather than the green check**, since a
conformance suite carries failures by design. Both adoptions here do exactly that.

Two Python-specific notes on top of the appendix:

- **Docker is not what decides it here.** `tests/e2e` needs Docker too, has needed it for years, and
  still runs in the default build on `ubuntu-latest`. The exclusion rests entirely on the second
  reason, that a conformance suite's honest output is red.
- **`--ignore` does not import the suite, so nothing checks that it still would**, and `mypy` here is
  configured over `src` alone. Hence `test-tck-collect` in both default tasks: it imports every test
  module and resolves the feature files while starting no container, which is the appendix's "keep it
  compiling" in the form Python has available. It cannot pass vacuously — pytest exits 5 on a
  directory that collects nothing and 4 on a path that does not exist, so a suite that moved out from
  under the task fails it rather than skipping it. `ignore_fail = "return_non_zero"` is what keeps the
  check reachable: poe otherwise aborts the sequence at the first failing subtask, and a compile check
  that only runs while the rest of the build is green is not a check.

## Extending it

Provider behaviour the specification does not describe — flagd's `fractional` targeting, a vendor's
own rollout rule — belongs in the same run rather than a second harness. Create an `extensions`
directory beside the module that calls `scenarios()`, with step definitions in a `conftest.py`:

```
tests/tck/
├── conftest.py                    # your step definitions
├── test_my_provider.py            # the fixtures and the one call, unchanged
└── extensions/
    └── fractional.feature
```

The directory is `tests/tck` because that is what the tasks above exclude and what `poe test-tck`
runs; the module inside it needs no `conformance` or `tck` in its name, since the directory is what
selects the suite. Both adoptions in this repository are laid out that way.

```python
# conftest.py
from pytest_bdd import then

from openfeature.contrib.tools.tck import TckState


@then("the fractional rule splits the population")
def fractional_splits(tck_state: TckState) -> None: ...
```

**No registration, no option and no new argument.** pytest collects `conftest.py` and pytest-bdd
resolves steps through the fixture system, so the canonical vocabulary is in scope beside your own,
and `tck_state` is the per-scenario state those steps use — your scenario runs against the provider
the suite registered, in the same lifecycle and reset. `feature_paths()` already includes an
`extensions` directory when there is one, so the `scenarios()` call never changes.

**Your scenarios cannot stand in for ours.** Canonical features are identified by their path under
`gherkin/` and yours under `extensions/`, and `extensions.py` refuses a file of yours under the
reserved prefix, or two that would share one uri. Both are reachable here, because pytest-bdd names a
feature file by its parent directory joined to its own name — so `extensions/gherkin/errors.feature`
would land on the canonical `errors.feature`'s uri, and a run could go green having asked the
adopter's questions instead of the specification's.

## Python-specific notes

**A boolean satisfies an Integer request**, because the client type-checks with
`isinstance(value, int)` and `bool` subclasses `int`. `boolean-flag` through `get_integer_details`
returns `True` with no error code where the specification requires the code default and
`TYPE_MISMATCH`, and the identical scenario passes in every other language's suite. Expect it in your
own run until a release carries [python-sdk#619](https://github.com/open-feature/python-sdk/issues/619);
the same cause reaches flagd-core's type check
([python-sdk-contrib#417](https://github.com/open-feature/python-sdk-contrib/issues/417)).

**Three steps reach the provider directly rather than through a client**, because going through the
SDK would test the registry's bookkeeping as much as the provider: the shutdown and re-initialise
steps call the registered instance's own `shutdown()` and `initialize()`, and the metadata step asks
it for `get_metadata()`. The registry is not told, so the SDK shuts the provider down once more when
the scenario ends — requirement 2.5.3 makes that harmless — and a direct call outlasting
`ready_timeout` fails its scenario rather than hanging the session.

**The SDK's `InMemoryProvider` is why this package ships `ControllableInMemoryProvider`** and why the
self-tests declare less than they otherwise would: it cannot update its flag set, which
[Appendix A][appendix-a] requires
([python-sdk#620](https://github.com/open-feature/python-sdk/issues/620)), never reads
`InMemoryFlag.state` ([python-sdk#627](https://github.com/open-feature/python-sdk/issues/627)), and
hands each variant back untouched, so it does not attempt numeric coercion at all — a permitted
choice rather than a defect, and the reason `@numeric-coercion` is simply not declared there.

## Conformance reports

Set `TCK_REPORT_DIR` and each suite writes **two** files: an envelope at `<dir>/<name>.json`,
conforming to the [report schema][report-schema], and the results it points at, at
`<dir>/<name>.ndjson`, which is a [Cucumber Messages][messages] stream.

```console
$ TCK_REPORT_DIR=./reports pytest
tck [in-memory]: report written to reports/in-memory.json with results in in-memory.ndjson (1 failed, 43 passed, 21 skipped)

$ jq -c .results reports/in-memory.json
{"format":"cucumber-messages","location":"in-memory.ndjson","digest":"sha256:c7e12a…"}
```

It is an environment variable rather than a `TckConfig` field so that emitting a report is a property
of the *run* and not of the code: CI sets it, a developer running the suite locally does not, and no
adopter changes a line to publish one. Unset means no report, which is not an error, and several
suites in one session each write their own pair, so flagd's two resolvers do not collide.

**A partial run is not a conformance run.** `-k`, `-m`, `--deselect`, or a test module that stopped
calling `scenarios()` on the canonical path each run fewer scenarios, and none of them is an error to
pytest — Go measured the consequence: a green run and a well-formed report covering one scenario out
of the whole canonical set, with nothing in the document saying so. So every run is checked against
the scenarios this distribution ships, and one that did not execute all of them writes no report and
names what it missed. A capability-gated skip **has** run — the question was put and declined — so
declining never trips this, and your own extension scenarios are not counted towards the canonical
set and cannot close a gap in it. `TCK_PARTIAL=1` lets you work on a single scenario without the
guard failing the run; it still writes no report, and Java spells the same escape hatch the same way.

**Why the results are not our format.** Per-scenario outcomes, tags, Scenario Outline row identity
and the executed feature source are already specified by Cucumber Messages, which is maintained,
cross-language, schema'd and emitted natively by cucumber-jvm; defining them again would create a
second format to version and two places for the same fact to disagree. So the envelope says what was
tested and what the provider claims, and the payload says what happened. The payload is referenced
rather than inlined because it carries the feature sources and is far larger than the envelope, and
`results.digest` is a SHA-256 over the exact bytes written, so a consumer can tell that what it
fetched is what the envelope described. Two things Messages cannot carry stay in the envelope:
`declaration`, which is an *input* to reading the results rather than a summary of them — only it
says whether a skipped scenario was declined — and the tested subject, for which no standard results
format has a slot.

**Reading the payload.** Appendix F requires a scenario skipped for an undeclared capability to be
reported as skipped with the reason and never as passed, and a consumer cannot check that against a
summary line, so the stream carries every scenario the run collected, gate-skipped ones included, as
Cucumber's own `SKIPPED`. Each is a `TestCase` referring to a `Pickle`, and a test case is as bad as
its worst step. Every test case carries two hook steps as well as its Gherkin steps, because pytest
runs a scenario in three phases and only the middle one executes steps: the before-hook is where a
capability skip's reason lands and the after-hook where a teardown failure does. The capability
responsible for a skip follows from the pickle's tags and the envelope's `declaration`, which is why
it is not transported once per scenario. And a pickle's `astNodeIds` are `[scenario id, table row
id]`, resolving in the `GherkinDocument` to exactly the cells the feature file wrote — which is what
tells the eleven rows of the type-mismatch matrix apart, one of which differs in outcome from its ten
siblings, exactly rather than by a naming convention every implementation would have to reproduce.

So the payload is not a transcription of pytest's summary. The one scenario the Python SDK cannot
satisfy is marked `xfail`, so pytest counts it as expected and exits zero; the provider still did not
satisfy it, and the stream says `FAILED`. The acknowledgement goes in the envelope's
`knownDeviations` instead — an expected failure is a recorded deviation, not an excused one.

**What identifies a report.** `tck.specRevision` comes from `spec_revision.json`, which the asset
sync generates from the submodule at build time, because the submodule is not in the wheel and an
installed copy has nothing left to ask; a build that cannot reach git records `unknown` rather than
inventing a commit. There is no asset tree hash: the payload's `Source` messages carry the executed
feature files verbatim, which answers "did these two runs ask the same questions" directly rather
than by proxy. `provider.name` is what the provider reports through its own metadata, not
`TckConfig.name`, which is chosen to read well in a failure message — `flagd-rpc` — and is therefore
reported as the *configuration*. `backend.controlApi` is read straight off the required `control_api`
member and the whole `backend` block is always written, both being in the schema's `required` arrays:
there is nothing to fall back to and nothing inferred, which is the point.

One gap is this implementation's rather than the suite's: **pytest-bdd emits no Cucumber Messages.**
It ships the legacy Cucumber JSON format and nothing for the ndjson protocol, so `messages.py` builds
the stream from the official types and re-parses the feature files for the AST node ids a pickle
refers to. If pytest-bdd ever emits Messages itself, that module should shrink to a shim. Whether a
report belongs inside a provider's released artifact is open on
[open-feature/spec#424](https://github.com/open-feature/spec/issues/424).

## Contributing

The Gherkin, the canonical flag set and the control-API document are **not owned by this
repository** — they are the artifacts in [open-feature/spec][spec], copied into the wheel and the
sdist at build time. So adopting needs no submodule and contributing does:

```bash
git submodule update --init tools/openfeature-tck/spec
poe test   # syncs the assets first; 289 passed, 42 skipped, 2 xfailed, no Docker
```

The copies under `src/` are gitignored, generated and carry a `DO-NOT-EDIT.txt`: a change goes to
[open-feature/spec][spec] first, then the submodule pin moves here, and that pin is the only record
of the revision this package targets. **The checkout is part of the sync, not something you
remember** — a rebase moves the gitlink and not the submodule's working tree, which is how an
adoption suite in another language ran a whole pass against the previous pin's feature files and
reported numbers identical to the run before it. So the sync checks the submodule out at the pinned
revision before copying and `poe test` depends on it: **the suite cannot run without a fresh sync,
and a sync cannot succeed against any revision but the pinned one.**
`OPENFEATURE_TCK_SPEC_UNPINNED=1` opts out while drafting a change to the assets; where the pin
cannot be read at all the sync warns and continues with the guarantee off, which covers an unpacked
sdist and a worktree whose `.git` points outside the running process's filesystem namespace, such as
a Windows worktree driven from WSL.

[report-schema]: https://github.com/open-feature/spec/blob/main/specification/assets/provider-tck/report/conformance-report.schema.json
[messages]: https://github.com/cucumber/messages
[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
