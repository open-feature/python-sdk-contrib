# OpenFeature TCK (Python)

A conformance suite any OpenFeature Python provider can adopt to verify that it implements the
provider contract of the specification.

Named `tck` rather than `provider-tck` because the name should say what the package *is*, not what
its current contents test: the entry point is options-shaped, so a suite for something other than a
provider can join it later instead of a second package duplicating the harness.

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

Two fixtures and one call. It uses **pytest-bdd**, the same runner the flagd provider and the flagd
testkit already use, so an adopting package gains no new test framework.

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

**The suite owns the container stack.** You name a Compose file, say which ports the provider
connects to, and build a provider from the endpoint you are handed. Starting the stack, discovering
the dynamically mapped host ports, building the HTTP control against the control API, waiting until
it accepts commands and tearing down afterwards are all the suite's - see
[The container stack](#the-container-stack). A provider with **no** backend supplies a
`BackendControl` of its own instead and needs no Compose file and no container tooling - see
[Providers with no backend](#providers-with-no-backend).

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

from openfeature.contrib.tools.tck import TckState


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

That line does not change when you add an extension. An adopter with no `extensions` directory gets
the canonical set alone, so adding one is a matter of creating a directory rather than of
configuring anything.

There used to be a second call, `features_path()`, which returned the canonical set on its own. It
is **gone**. The two differed by one character at the call site and the shorter one silently dropped
the extensions directory, so reaching for it produced a green run over fewer scenarios than the
adopter believed had run — which is the worst failure mode available to a conformance suite, because
nothing is there to notice. `canonical_root()` is the supported way to reach the packaged directory
for anything that is not "the scenarios to run".

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
        Declared: @events @large-integers @object @variants
```

| Capability | Tag | Meaning |
| --- | --- | --- |
| `Capability.LIFECYCLE` | `@lifecycle` | reaches its backend during initialisation, observably and promptly |
| `Capability.EVENTS` | `@events` | emits lifecycle events at all |
| `Capability.STALE` | `@stale` | enters `STALE` and emits `PROVIDER_STALE` on backend loss |
| `Capability.CONFIGURATION_CHANGE` | `@configuration-change` | detects configuration changes and emits `PROVIDER_CONFIGURATION_CHANGED` |
| `Capability.OBJECT` | `@object` | supports structured flag values |
| `Capability.VARIANTS` | `@variants` | names the variant it resolved, which [Requirement 2.2.4](https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md) makes a `SHOULD` and `types.md` types as optional |
| `Capability.DISABLED_FLAGS` | `@disabled-flags` | resolves a flag disabled in the management system to the code default |
| `Capability.UNAVAILABLE_INIT` | `@unavailable` | reports an error state instead of hanging against a dead backend |
| `Capability.NUMERIC_COERCION` | `@numeric-coercion` | coerces between integer and float only when lossless, else `TYPE_MISMATCH` |
| `Capability.LARGE_INTEGERS` | `@large-integers` | resolves integers up to 2^53 − 1 exactly; undeclarable where the SDK's integer accessor is 32-bit |
| `Capability.REINITIALIZATION` | `@reinitialization` | can be initialised again after `shutdown`, which [Requirement 2.5.2](https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md) permits rather than requires |
| `Capability.TARGETING` | `@targeting` | resolves a flag differently for a matching evaluation context |
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

`@variants` was the one found the hard way, and it is the reason the rule above is worth stating
twice. Every evaluation scenario used to assert a variant, which reads as obviously correct until a
backend with no variant concept for a plain flag is put under test: its evaluation response carries
no such key, the provider never receives one, and no seeding can produce one. Ten scenarios failed a
conformant provider for something its author could not fix, and nothing could be recorded as a
`KnownDeviation` because there was no capability to hang one on.
[Requirement 2.2.4](https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md)
is a **SHOULD** and `types.md` types the field `variant (string, optional)`, so the suite was
asserting a `MUST` neither of them states. Since spec revision `26362f85` the variant assertions
live in one gated Scenario Outline of eight rows; the value and reason assertions stay untagged,
because 2.2.3 makes the value a `MUST`.

`@targeting` was **reserved and undeclarable** until the same revision, on the reading that targeting
is backend evaluation logic and out of scope. The scope argument still holds — its three scenarios do
not test how a backend evaluates a rule — but the conclusion did not: they exist to show the context
reached the backend at all, which is a property of the provider and of nothing else.
`targeting-key-flag` is the one flag in the canonical set with a rule, specified by behaviour rather
than syntax (resolve `hit` when the targeting key is exactly `5c3d8535-f81a-4478-a6d3-afaa4d51199e`),
and a matching context resolving to a different value is what catches a provider that drops the
context — no echo endpoint on the control API required. The three scenarios are the matching context,
the non-matching one and no context at all; the second and third are not padding, since a provider
that always returned the targeted value would pass the first and one that refuses to evaluate a rule
with no targeting key is caught by the third.

`@disabled-flags` is gated because it needs two things and only one of them comes for free. The
caller's default value is held by the provider, which always has it. What the provider also needs is
a **signal** that the flag was disabled, told apart from an ordinary resolution and from a missing
flag — and that belongs to the backend and its protocol. One with no disabled state, or one that
answers `FLAG_NOT_FOUND` for a disabled flag, gives the provider nothing to act on.

[Appendix F][appendix-f] draws the line elsewhere — a provider whose backend decides, *"such as one
speaking OFREP, cannot: the server never sees the caller's default, so it has no way to return it"* —
and what this suite measured does not bear that out. flagd's RPC resolver is a remote evaluator by
exactly that description and satisfies the capability: the server answers reason `DISABLED` with no
variant and no value, and the resolver substitutes the caller's default locally on that signal.
flagd's OFREP endpoint answers the same flag with `{"reason": "DISABLED"}` and no `value` and no
`variant` — the same signal in another envelope — and the Python OFREP provider already falls back to
the caller's default for the absent value. It fails these scenarios for a reason unrelated to
architecture, which [its own suite](../../providers/openfeature-provider-ofrep/tests/tck/test_ofrep_conformance.py)
records. The discrepancy belongs upstream rather than papered over here; what it changes locally is
only what a withheld declaration may be read as — not necessarily an impossibility, so read the
adoption's own note for which it was. Withholding still needs no `KnownDeviation`, for the reason
every gated capability does: a deviation records a gap in behaviour the provider is *required* to
have, and this one is optional.

Nothing in the specification says what a provider owes a disabled flag:
[Requirement 1.4.7](https://github.com/open-feature/spec/blob/main/specification/sections/01-flag-evaluation.md)
is about the SDK propagating whatever reason arrived, and 2.2.5 only lists `DISABLED` among the
reason strings a provider **may** use. So [Appendix F][appendix-f] states the behaviour, the way it
does for `@numeric-coercion`, and gates it. Since spec revision `009afe06` the canonical set carries
four `disabled-*` flags mirroring `boolean-flag`, `string-flag`, `integer-flag` and `float-flag`
exactly, differing only in `state`, and one Scenario Outline of four rows asserts that each resolves
to the caller's default. Each row's default differs from the flag's configured value, so a provider
that ignores the state is caught on the value alone — 2.2.3, a `MUST`. The rows assert neither the
reason, which would rest on 2.2.5's `SHOULD` and its "some other string", nor the variant, since a
disabled flag has resolved none: `@disabled-flags` and `@variants` deliberately do not compose.

Untagged scenarios are mandatory and always run. `capabilities` defaults to every *declarable*
capability — `DECLARABLE_CAPABILITIES` — and you should narrow it rather than widen it: start from
the default, run the suite, and remove only what your provider genuinely cannot do.

Leaving a capability out is the only way to withhold it, and one skip carrying its reason is the
whole mechanism: the scenario's tags say what was asked, the declaration says whether it was
claimed, and the skip says why it was not. A capability that cannot hold in a language *at all* —
`@numeric-coercion` where the language has a single numeric type, `@large-integers` on a 32-bit
accessor — is a property of the SDK rather than of the provider, and
[Appendix F][appendix-f] records it once instead of every report restating it.

A reserved capability is documented so the vocabulary has a place for it once scenarios exist, and
until then it **must not be declared**. Nothing carries the tag, so declaring it cannot be verified,
cannot produce a skip, and tells anyone reading the declaration only that something was claimed and
nothing examined. `TckConfig` raises if you name one in `capabilities`, and
`DECLARABLE_CAPABILITIES` excludes them — which is the case that matters, because "every capability
except X" is how a reserved tag gets declared by accident rather than by decision. One
implementation's published conformance report asserts `@targeting` and `@caching` for exactly that
reason, back when both were reserved.

`@caching` is the only reserved tag left. Leaving one reserved once it *has* scenarios would be the
mirror of the mistake the set exists to prevent — a capability that can be verified, refused the
chance — so `@targeting` moved out of it the moment the specification gave it three.

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

One further field on `TckConfig` says something a capability set cannot, and it is a declaration
rather than a switch: it changes neither which scenarios run nor what they assert.

`known_deviations` acknowledges a gap against something the specification does *not* treat as
optional. It is an acknowledgement and not an excuse: the scenario still fails and the suite still
fails with it. What the declaration adds is that the gap was known rather than a surprise.

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

- **`summary` is required.** A deviation with no summary records that something is wrong without
  saying what, which leaves a reader worse off than the bare skip or failure it accompanies.
- **`issue` is optional**, and `KnownDeviation.untracked(summary=...)` is the form for a gap that is
  not tracked anywhere yet. Naming an untracked defect is still what separates it from a capability
  the provider chose to withhold; prefer the tracked form as soon as there is somewhere to point.
- **`capability` is optional**, and left out when the gap is against a mandatory, ungated scenario.
  A reserved capability is refused: no scenario carries the tag, so there is nothing to deviate
  from.

It is legitimate in two shapes, and **prefer the first**:

1. **The capability is declared, the scenario runs, and it fails.** The failure stays visible and
   the deviation says it is known and why.
2. **The capability is withheld and its scenarios skip.** Legitimate only when the provider cannot
   attempt the behaviour at all, so running the scenario would establish nothing. The deviation then
   explains the absence, so a reader can tell a defect from a design decision.

Withdrawing a capability *in order to* turn a failing scenario into a skip is the failure mode this
field exists to prevent. Where the specification permits the choice, withholding the capability
**is** the honest report and a deviation entry would assert a defect that does not exist.

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

`HttpControl` is built on `urllib.request` alone, so the TCK gains no HTTP client. You do not build
one yourself when you use the Compose harness below: it is handed to you as `tck_backend.control`,
already awaited ready.

### The container stack

The suite starts it. An adopter used to write the container wrapper — and every adopter wrote the
same one, which is why the flagd adoption alone carried a 122-line `conftest.py` and a 170-line
`suite.py` of it. `ComposeBackend` is the whole declaration:

| field | required | default | meaning |
| --- | --- | --- | --- |
| `compose_file` | yes | — | path to the Compose file, resolved relative to the package directory |
| `backend_ports` | yes | — | container-internal ports the **provider** connects to. The control port is exposed automatically and must not be listed here |
| `backend_service` | no | `"backend"` | the Compose service hosting both the control API and the backend |
| `control_port` | no | `8080` | container-internal port of the control API |
| `additional_ports` | no | `{}` | extra service to ports, for a stack with more than one service. Resolved through the endpoint by service name |
| `configuration` | no | `"default"` | the configuration name passed to `POST /start` |
| `startup_timeout` | no | `60.0` | seconds to wait for the stack and its control API to become reachable |

Those names and defaults are fixed across all four languages' TCKs, so a provider shipped in two of
them writes one Compose file and two declarations against it.

`tck_backend` is a session-scoped fixture this package's plugin supplies, and it yields two things:

- `tck_backend.control` — the `HttpControl`, already awaited ready. Hand it to `TckConfig.control`.
  One per stack: it remembers whether a disconnect left the backend down, so two suites driving the
  same backend must share it.
- `tck_backend.endpoint` — `host`, `port(internal)` and `port(internal, service=...)`. This is a
  **factory argument, not a field**: the mapped ports do not exist until the stack is up, which is
  why `TckConfig.new_provider` is a factory called once per scenario.

Your Compose file must **not pin host ports**. Docker assigns them dynamically and the harness
discovers them after startup; a pinned host port makes the suite unrunnable in parallel and collides
with whatever you already have listening. Declaring `backend_ports` is what lets the harness say
"the Compose file does not publish 8013" at startup rather than leaving you with a provider that
cannot connect three scenarios later.

Startup is a real readiness check rather than a pause: the stack comes up with
`docker compose up --wait`, then every declared port is waited on until it accepts a connection,
then `HttpControl.await_ready()` probes `GET /healthz` until the control API answers. There is
deliberately **no settle after a control call**. Java had a fixed 50ms one; flagd-testbed#394 makes
`POST /start` block until the flags are evaluable, so the sleep covered a window that no longer
exists — and a suite that sleeps instead of holding the control API to its promise stops being able
to detect when the promise breaks. If dropping it makes an adoption flaky, that is a testbed defect
worth filing, not a sleep worth restoring.

`testcontainers` is an **optional** extra rather than a dependency:

```
pip install 'openfeature-tck[compose]'
```

An in-memory adopter should not have to install container tooling to run a suite that never starts a
container, so `compose.py` imports it lazily and says so if it is missing.

If you want the fixture under a different name or scope, `run_compose_backend()` is the generator
behind it:

```python
@pytest.fixture(scope="session")
def tck_backend():
    yield from run_compose_backend(ComposeBackend(...))
```

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

Four, all confirmed by running the suite rather than by reading code.

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

### 4. The in-memory provider ignores a flag's state

`InMemoryFlag` has a `State` enum with an `ENABLED` and a `DISABLED` member, takes one in its
constructor, and **never reads it**: `InMemoryFlag.resolve` returns the default variant's value with
reason `STATIC` whatever the state, and `InMemoryProvider._resolve` looks only for a missing key. So
all four `disabled-*` flags are served exactly as their enabled counterparts are.

`canonical_flag_set` is not where this stops. `_decode_canonical_flags` reads the canonical file's
`"state": "DISABLED"`, validates it against `InMemoryFlag.State` and passes it through faithfully —
the self-tests pin that it reaches exactly those four flags and no others. The state survives
decoding and then has no effect.

Measured before the tag was gated: all four rows failed on the value in both in-memory suites, with
`disabled-boolean-flag` resolving to `True` against a caller default of `false`. So neither suite
declares `@disabled-flags` and the four scenarios are skipped with that reason.

Unlike finding 3 this is a field the SDK offers and does not honour, which is closer to a defect than
to a choice — but the capability is optional, so the honest report is still a withheld declaration
rather than a `KnownDeviation`. It is not filed against the SDK yet.

## Where the assets come from

The Gherkin feature files, the canonical flag set and the control-API document are **not owned by
this repository**. They are the language-agnostic conformance artifacts defined in
[open-feature/spec][spec] under `specification/assets/provider-tck/`, and every language's TCK ships
the same ones — which is the only reason a conformance claim means the same thing in Python as it
does in Java.

**Adopting this package needs no submodule.** The assets are copied into the wheel and the sdist at
build time, so `pip install openfeature-tck` gives you everything the suite runs on.

**Contributing to this package does.** The spec is a git submodule at
`tools/openfeature-tck/spec`, and the copies under
`src/openfeature/contrib/tools/tck/` are gitignored and generated:

```bash
git submodule update --init tools/openfeature-tck/spec
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
| `test_in_process_control` | `InProcessControl` and the canonical flag set | pins what the Gherkin cannot assert about itself, including that the in-memory flag set is decoded from `canonical-flags.json` — every flag served under the file's own default variant, with the Python type the file wrote, and `state` reaching exactly the four `disabled-*` flags |
| `test_lifecycle_steps` | the steps that call the provider directly | the in-memory suites skip `@lifecycle`, so the shutdown, re-initialise and metadata steps are driven against a recording provider instead |
| `test_declaration` | what a `TckConfig` claims | none of it is observable in a pass or a fail, so nothing else would catch it |
| `test_extensions` | an adopter's own scenarios | an extension runs inside the canonical suite, changes nothing for an adopter who has none, and cannot take a canonical scenario's identity |
| `test_http_control` | `HttpControl` | the `/reset` fallback, the disconnect bookkeeping and the control-API it reports, against a stubbed control API |

```
163 passed, 35 skipped, 2 xfailed
```

No Docker and no network beyond loopback. The conformance suites take under a second;
`test_extensions` takes most of the rest, because the properties it checks are properties of a whole
pytest session and it runs a generated adoption in a subprocess to check them.

Neither in-memory suite declares `@lifecycle`, so the six lifecycle scenarios — three about
initialisation, three about shutdown — are skipped in both. That is the point: with no backend to
reach, the initialisation ones would pass without testing anything — which is what they did while the
feature was gated on `@events`. Neither declares `@numeric-coercion` either, for the reason in
finding 3, so its three scenarios are skipped too. Neither declares `@targeting`: both resolve the
same decoded flag set, and `canonical_flag_set` deliberately ignores `targeting-key-flag`'s rule
rather than becoming a second implementation of somebody else's evaluator, so those three scenarios
are skipped as well. Neither declares `@disabled-flags` either, for the reason in finding 4 — the
state reaches the flag set and the SDK's provider never reads it — so its four rows are skipped in
both. Both declare `@variants`, since an in-memory flag set is keyed by variant name.

## Known gaps

- **Evaluation context passthrough is verified only for the targeting key.** `targeting-key-flag`
  resolves differently for a matching context, so the `@targeting` scenarios catch a provider that
  drops the context — no echo operation needed for that. What is still unverified is that the
  *whole* context arrives intact: a provider that forwards the targeting key and silently discards
  every other attribute passes. That needs either an echo operation on the control API or a second
  canonical flag whose rule keys on a custom attribute.
- **Caching, hooks and flag metadata** are not covered.

[appendix-a]: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
[appendix-f]: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
[spec]: https://github.com/open-feature/spec
[tracking]: https://github.com/open-feature/spec/issues/417
