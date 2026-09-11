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

Put them in the same run instead. Create a directory named `extensions` beside the module that
calls `scenarios()`, and write step definitions for whatever is new in a `conftest.py` beside it:

```
tests/
├── conftest.py                    # your step definitions
├── test_conformance.py            # the fixture and the one call, unchanged
└── extensions/
    └── fractional.feature
```

```python
# conftest.py
from pytest_bdd import then

from openfeature.contrib.tools.provider_tck import TckState


@then("the fractional rule splits the population")
def fractional_splits(tck_state: TckState) -> None: ...
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

That line does not change when you add an extension, and it is the only difference from
`scenarios(features_path())` — which still works and still sees only the canonical set. An adopter
with no `extensions` directory runs exactly what they ran before: same scenarios, same count.

### Your scenarios cannot stand in for ours

Every feature file carries a uri, and it is how a canonical scenario is told from an adopter's:
canonical files are the ones under the `gherkin/` prefix and yours are under `extensions/` — the
prefix Go and JavaScript mount theirs under too, so a consumer holding conformance reports from
several languages applies one rule. Neither prefix is this package's to choose: Appendix F
identifies a canonical feature by its path *relative to the specification's asset directory*, which
is what makes it `gherkin/`. The prefix is derived from where a file *is*, not from what the runner
called it, and `extensions.py` reports two cases that derivation cannot rule out:

- **A feature file of yours under the reserved `gherkin/` prefix.** Handing `scenarios()` a
  directory of your own named `gherkin` is the one route left to a canonical-looking uri.
- **Two feature files that would share one uri.** A record of what ran holds one copy of a feature
  file per uri, so the second file's scenarios would be attributed to the first file's.

This is not hypothetical. Java's suite found that a same-named feature file in a second classpath
root *replaced* the canonical one, and the run went green having asked the adopter's questions
instead of the specification's — the worst outcome available to a conformance suite. The Python
route to the same place is narrower and just as quiet: pytest-bdd names a feature file by its parent
directory joined to its own name, so `extensions/gherkin/errors.feature` arrives under the uri
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
        Declared: @events @large-integers @object
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
| `Capability.LARGE_INTEGERS` | `@large-integers` | resolves integers up to 2^53 − 1 exactly; undeclarable where the SDK's integer accessor is 32-bit |
| `Capability.REINITIALIZATION` | `@reinitialization` | can be initialised again after `shutdown`, which [Requirement 2.5.2](https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md) permits rather than requires |
| `Capability.TARGETING` | `@targeting` | reserved; **not declarable** — no scenarios yet |
| `Capability.CACHING` | `@caching` | reserved; **not declarable** — no scenarios yet |

`@lifecycle` and `@events` are deliberately separate, and the split matters in both directions. An
SDK dispatches `PROVIDER_READY` around `initialize` for *any* provider, so a provider declaring only
`@events` passes the readiness scenario without demonstrating anything — a `NoOpProvider` passes it
identically. Meanwhile a stateless provider has a real initialisation to verify but no event stream
of its own to declare `@events` for, and gating on `@events` shut it out of a scenario it should be
held to.

`@reinitialization` is separate from `@lifecycle` for a subtler reason.
[Requirement 2.5.2](https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md)
says a provider **SHOULD** revert to its uninitialized state after `shutdown`, and its supporting
text adds that *"some providers **may** allow reinitialization from this state"*. Reuse is therefore
permitted, not required: a provider that releases its client on shutdown and declines to be started
again is exercising a choice the specification offers it, so withholding this capability needs no
`KnownDeviation` entry.

The scenario was untagged until spec revision `fc99d5ac`, on the reading that reverting to the
uninitialized state is observable as exactly one thing — being initialisable again. That inference
does not hold, and asserting it unconditionally reported a permitted choice as a conformance failure.
A false failure is the mirror image of a vacuous pass, and this suite cares about both. Reverting the
state is not separately observable either — a provider that reverts but refuses reuse presents
identically to one that did neither — so the gated reuse scenario is the only assertion the
requirement admits. It is worth keeping for the providers that do offer reuse, because releasing the
client on shutdown while leaving an initialised flag set behind is easy to write and leaves the
provider evaluating against a closed connection rather than failing outright.

One practical note, because it is easy to get wrong: `@reinitialization` **narrows** `@lifecycle`
rather than standing beside it. The scenario lives in `lifecycle.feature`, which carries `@lifecycle`
at the feature level, so the scenario inherits it and carries both tags — and the gate skips a
scenario when *any* capability gating it is undeclared. Reuse is therefore exercised only by an
adoption declaring `Capability.LIFECYCLE` **and** `Capability.REINITIALIZATION`; declaring the latter
alone leaves the scenario skipped on `@lifecycle` and the declaration unverified. So a provider that
withholds `LIFECYCLE` has never run this scenario, and has no evidence either way on which to declare
reuse.

Untagged scenarios are mandatory and always run. `capabilities` defaults to every *declarable*
capability — `DECLARABLE_CAPABILITIES` — and you should narrow it rather than widen it: start from
the default, run the suite, and remove only what your provider genuinely cannot do.

A reserved capability is documented so the vocabulary has a place for it once scenarios exist, and
until then it **must not be declared**. Nothing carries the tag, so declaring it cannot be verified,
cannot produce a skip, and tells anyone reading the declaration only that something was claimed and
nothing examined. `TckConfig` raises if you name one in `capabilities` or in `not_applicable`, and
`DECLARABLE_CAPABILITIES` excludes them — which is the case that matters, because "every capability
except X" is how a reserved tag gets declared by accident rather than by decision. One
implementation's published conformance report asserts `@targeting` and `@caching` for exactly that
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

Both halves are tested, and a provider declaring the tag must satisfy all three scenarios: `float-flag`
(`0.5`) requested as an integer is a `TYPE_MISMATCH`; `integral-float-flag` (`10.0`) requested as an
integer is `10`; `integer-flag` (`10`) requested as a float is `10.0`. Rejecting every float is an easy
way to pass the first, and the other two are what stop it.

The width of the integer accessor is the related property, and it is a capability of its own because
it belongs to the SDK rather than to the provider. Every language can ask for 2^31 − 1, so that
precision scenario is untagged; only the one asking for 2^53 − 1 carries `@large-integers`. A Python
`int` is unbounded, so a Python provider declares it unless something of its own — a 32-bit field in
its wire format, a float on the way through — narrows the value.

### Steps that reach the provider directly

Everything the suite asks of a provider goes through an OpenFeature client, as an application's
would — except three steps. `the provider is shut down` and `the provider is initialized again` call
the provider's own `shutdown()` and `initialize()` on the registered instance, and
`the provider metadata name should not be empty` asks it for `get_metadata()`. Going through the SDK
would test the registry's bookkeeping as much as the provider, and Appendix B already does that; it
would also make a double shutdown impossible to express, since the registry calls `shutdown` once
per registration.

The registry is not told. The client keeps pointing at the same instance, so an evaluation after
re-initialising reaches the very object that was shut down and brought back. When the scenario ends,
the SDK shuts the provider down once more on its own — requirement 2.5.3 makes that second call
harmless, and the suite relies on it. A direct call that outlasts `TckConfig.ready_timeout` is given
up on and fails its scenario with a message rather than hanging the session.

### Declaring more than a capability set

Two further fields on `TckConfig` say things a capability set cannot, and both are declarations
rather than switches: neither changes which scenarios run or what they assert.

`not_applicable={Capability.X: "why"}` is for a capability that *cannot* hold rather than one you
chose not to declare. The suite treats the two identically — the scenarios are skipped either way,
with the reason — but collapsing them misrepresents a provider, and whole languages with it:
`@numeric-coercion` is unsatisfiable in JavaScript because the language has no integer type, and
recording that as a choice would show every JavaScript provider as declining something none of them
can have. Declining an optional feature is a choice; an impossibility is not.

`known_deviations=(KnownDeviation(issue=..., summary=...),)` acknowledges a gap against something the
specification does *not* treat as optional, with somewhere it is tracked. It is an acknowledgement
and not an excuse: the scenario still fails and the suite still fails with it. What the declaration
adds is that the gap was known rather than a surprise.

## Controlling the backend

`BackendControl` is the single seam between the scenarios and whatever manipulates the backend. Step
definitions never talk to a backend directly, which is why the same Gherkin runs unchanged against a
containerised backend and against a provider manipulated in-process.

**If your provider talks to a backend, drive it over the HTTP control API** — the document is
available as `control_api_spec()`, and `HttpControl` is the client for it. That API is the normative
contract for those providers, and it is what makes a conformance claim portable: another language's
TCK drives the same endpoints against the same stack and must get the same answers.

```python
control = HttpControl(f"http://localhost:{container.get_launchpad_port()}")
```

`HttpControl` is built on `urllib.request` alone, so the TCK gains no HTTP client and no container
dependency. **Orchestrating the stack stays with you**, where the vendor-specific knowledge already
lives — which compose file, which services, which internal ports. That is a deliberate trade against
the "provider authors write no test infrastructure" goal, and worth revisiting once a second
containerised adopter shows what is actually common.

Two of its behaviours are worth knowing about:

- **`/reset` is optional and the fallback is automatic.** `prepare_scenario()` prefers `POST /reset`,
  which restores the flag baseline with no availability blip; a backend without it answers 404 or
  501 and the client falls back to `POST /start?config=default`. The probe happens once per suite.
  flagd-testbed's launchpad registers only `/start`, `/restart`, `/stop` and `/change`, so that
  fallback is the normal path today.
- **After a disconnect it starts rather than resets.** `/reset` restores flag *state*; it is not
  specified to bring a stopped backend back up.

Two of the API's requirements are easy to get wrong:

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

Three, all confirmed by running the suite rather than by reading code.

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

### 3. The in-memory provider does not coerce numbers

`integral-float-flag` (`10.0`) requested as an integer returns the code default with `TYPE_MISMATCH`,
and `integer-flag` (`10`) requested as a float does the same. The provider hands each variant back
untouched and the client's type check is `isinstance`-based, so neither lossless direction happens.
The lossy scenario passes — every float is rejected — which is exactly the shortcut the two lossless
scenarios exist to catch.

This is not a defect: `@numeric-coercion` is optional, and the specification does not define the
behaviour. So neither in-memory self-test declares the tag, and the three scenarios are skipped with
that reason rather than failing.

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

## The self-tests

| Suite | Subject | Why |
| --- | --- | --- |
| `test_in_memory_conformance` | the SDK's `InMemoryProvider` | reference adoption for a backend-less provider |
| `test_controllable_conformance` | `ControllableInMemoryProvider` | the only suite that exercises the configuration-change path — see finding 2 |
| `test_in_process_control` | `InProcessControl` and the canonical flag set | pins what the Gherkin cannot assert about itself, including that the in-memory flag set mirrors `canonical-flags.json` type for type |
| `test_lifecycle_steps` | the steps that call the provider directly | the in-memory suites skip `@lifecycle`, so the shutdown, re-initialise and metadata steps are driven against a recording provider instead |
| `test_declaration` | what a `TckConfig` claims | none of it is observable in a pass or a fail, so nothing else would catch it |
| `test_extensions` | an adopter's own scenarios | an extension runs inside the canonical suite, changes nothing for an adopter who has none, and cannot take a canonical scenario's identity |
| `test_http_control` | `HttpControl` | the `/reset` fallback, the disconnect bookkeeping and the control-API it reports, against a stubbed control API |

```
125 passed, 21 skipped, 2 xfailed
```

No Docker and no network beyond loopback. The conformance suites take under a second;
`test_extensions` takes most of the rest, because the properties it checks are properties of a whole
pytest session and it runs a generated adoption in a subprocess to check them.

Neither in-memory suite declares `@lifecycle`, so the six lifecycle scenarios — three about
initialisation, three about shutdown — are skipped in both. That is the point: with no backend to
reach, the initialisation ones would pass without testing anything — which is what they did while the
feature was gated on `@events`. Neither declares `@numeric-coercion` either, for the reason in
finding 3, so its three scenarios are skipped too.

## Known gaps

- **Evaluation context passthrough is unverifiable.** The scenarios build evaluation contexts but
  cannot assert one *reached* the backend. That needs an echo operation on the control API.
- **No shared containerised-backend helper.** `HttpControl` drives the control API, but starting the
  stack and discovering its mapped ports is still each adopter's own code. Abstracting that from a
  single example tends to produce the wrong abstraction; it should wait for a second adopter.
- **Caching, hooks and flag metadata** are not covered.

[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
