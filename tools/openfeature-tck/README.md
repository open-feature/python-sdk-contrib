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
| `Capability.STRING_TYPING` | `@string-typing` | reports `TYPE_MISMATCH` for a boolean or integer flag asked for as a string |
| `Capability.FULLY_TYPED_VALUES` | `@fully-typed-values` | records a native type for float and structured values too |
| `Capability.LARGE_INTEGERS` | `@large-integers` | resolves integers up to 2^53 − 1 exactly |
| `Capability.REINITIALIZATION` | `@reinitialization` | can be initialised again after `shutdown` |
| `Capability.TARGETING` | `@targeting` | resolves differently for a matching evaluation context |
| `Capability.STANDARD_REASONS` | `@standard-reasons` | uses the standard resolution reasons with their standard meanings |
| `Capability.CACHING` | `@caching` | reserved; **not declarable** — no scenarios yet |

Untagged scenarios are mandatory and always run. `capabilities` defaults to
`DECLARABLE_CAPABILITIES`; narrow it rather than widen it. Tags compose, so declaring
`@reinitialization` without the `@lifecycle` its feature carries leaves that scenario skipped, and
`@fully-typed-values` without `@string-typing` runs nothing at all.
**What counts as "cannot do" is [Appendix F][appendix-f]'s rules for declaring**; the adoptions here
cite them rather than restating them, and so should yours.

`TckConfig` refuses two declarations at construction rather than letting them reach a report: a
**reserved** capability, which no scenario carries, and one this language's SDK **cannot express** —
the two errors and the two skip reasons deliberately differ, and a scenario arriving with a reserved
tag fails the run. So does a canonical scenario carrying a tag this table does not have: an unknown
tag gates nothing, so its scenarios stay mandatory for every adopter, and the suite would go on
demanding a behaviour the specification has just made optional.
`INEXPRESSIBLE_CAPABILITIES` is **empty in Python**, measured rather than assumed:
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

## Contributing

The Gherkin, the canonical flag set and the control-API document are **not owned by this
repository** — they are the artifacts in [open-feature/spec][spec], copied into the wheel and the
sdist at build time. So adopting needs no submodule and contributing does:

```bash
git submodule update --init tools/openfeature-tck/spec
poe test   # syncs the assets first; 227 passed, 41 skipped, 2 xfailed, no Docker
```

The copies under `src/` are gitignored, generated and carry a `DO-NOT-EDIT.txt`: a change goes to
[open-feature/spec][spec] first, then the submodule pin moves here, and that pin is the only record
of the revision this package targets. **The checkout is part of the sync, not something you
remember** — a rebase moves the gitlink and not the submodule's working tree, which is how an
adoption suite in another language ran a whole pass against the previous pin's feature files and
reported numbers identical to the run before it. So the sync checks the submodule out at the pinned
revision before copying and `poe test` depends on it: **the suite cannot run without a fresh sync,
and a sync cannot succeed against any revision but the pinned one.**
`OPENFEATURE_TCK_SPEC_UNPINNED=1` opts out while drafting a change to the assets.

**A check that cannot run fails rather than skipping**, which is [Appendix F][appendix-f]'s
run-integrity rule and the reverse of what this used to do: the environments where the pin was
unreadable are the ones where a rebase leaves the assets stale, so the check went quiet exactly where
it mattered. It also has one environment fewer to abandon — a worktree whose `.git` names a path
outside the running process's filesystem namespace, such as a Windows worktree driven from WSL, no
longer defeats it, because the pin is read by naming the superproject that git could not find. What
remains exempt is an unpacked sdist, which has no submodule, no pin and nothing that could have
drifted from one.

[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
