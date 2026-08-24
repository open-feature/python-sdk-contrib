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
with the distribution, so **you need no git submodule**.

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
        Declared: @events @object @strict-numeric-typing
```

| Capability | Tag | Meaning |
| --- | --- | --- |
| `Capability.EVENTS` | `@events` | emits lifecycle events at all |
| `Capability.STALE` | `@stale` | enters `STALE` and emits `PROVIDER_STALE` on backend loss |
| `Capability.CONFIGURATION_CHANGE` | `@configuration-change` | detects configuration changes and emits `PROVIDER_CONFIGURATION_CHANGED` |
| `Capability.OBJECT` | `@object` | supports structured flag values |
| `Capability.UNAVAILABLE_INIT` | `@unavailable` | reports an error state instead of hanging against a dead backend |
| `Capability.STRICT_NUMERIC_TYPING` | `@strict-numeric-typing` | does not coerce between integer and float |
| `Capability.TARGETING` | `@targeting` | reserved; no scenarios yet |
| `Capability.CACHING` | `@caching` | reserved; no scenarios yet |

Untagged scenarios are mandatory and always run. `capabilities` defaults to everything — narrow it
rather than widening it: start from the default, run the suite, and remove only what your provider
genuinely cannot do.

`@strict-numeric-typing` deserves a note, because unlike the others it is **not** an optional
feature. The specification requires `TYPE_MISMATCH` when the requested type cannot be satisfied, and
narrowing `0.5` to `0` loses information silently. It is a capability only so a provider with the
defect can adopt today and see the gap reported explicitly rather than being unable to adopt at all.
Not declaring it is an admission of a known bug.

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

## The self-tests

| Suite | Subject | Why |
| --- | --- | --- |
| `test_in_memory_conformance` | the SDK's `InMemoryProvider` | reference adoption for a backend-less provider |
| `test_controllable_conformance` | `ControllableInMemoryProvider` | the only suite that exercises the configuration-change path — see finding 2 |
| `test_in_process_control` | `InProcessControl` | pins what the Gherkin cannot assert about itself |

```
56 passed, 7 skipped, 2 xfailed
```

No Docker, no network, under a second.

## Known gaps

- **The assets are vendored, not submoduled.** `features/` and `flag_data/` are copies of
  `specification/assets/provider-tck/` in [open-feature/spec][spec]. Changes belong there and are
  copied here; a follow-up will source them from a submodule at build time, as
  `openfeature-flagd-api-testkit` already does for the flagd test harness.
- **Evaluation context passthrough is unverifiable.** The scenarios build evaluation contexts but
  cannot assert one *reached* the backend. That needs an echo operation on the control API.
- **No HTTP control client yet.** It arrives with the first containerised adopter.
- **Caching, hooks and flag metadata** are not covered.

[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
