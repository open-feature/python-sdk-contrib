"""Optional parts of the provider contract, and the Gherkin tags that gate them."""

from __future__ import annotations

import typing
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

__all__ = ["Capability"]


class Capability(str, Enum):
    """An optional part of the OpenFeature provider contract.

    Not every provider implements every part of the specification. A provider
    backed by a static file has no meaningful notion of going stale; one with no
    streaming transport cannot emit configuration-change events. Rather than
    forcing such providers to fail scenarios they were never going to satisfy,
    each declares what it supports through :attr:`TckConfig.capabilities`.

    Every capability corresponds to exactly one Gherkin tag. pytest-bdd turns
    those tags into pytest markers, and a scenario carrying a marker whose
    capability was not declared is skipped with the reason reported -- never
    passed. A conformance suite that quietly goes green on scenarios it did not
    run is worse than no suite at all.

    Scenarios with no capability tag are mandatory and always run.

    Two kinds of capability are refused rather than declared, and they are
    refused for different reasons and with different messages:
    :data:`RESERVED_CAPABILITIES`, which no scenario anywhere carries yet, and
    :data:`INEXPRESSIBLE_CAPABILITIES`, whose question this language's SDK cannot
    put at all. :data:`DECLARABLE_CAPABILITIES` is what is left.
    """

    LIFECYCLE = "lifecycle"
    """Provider reaches its backend during initialisation, observably and promptly.

    Deliberately separate from :attr:`EVENTS`, because the two are independent in
    both directions.

    An SDK dispatches ``PROVIDER_READY`` around ``initialize`` for *any*
    provider, so a provider that declares ``EVENTS`` passes the readiness
    scenario without demonstrating anything -- a ``NoOpProvider`` passes it
    identically. Gating on ``EVENTS`` therefore made the scenario vacuous for
    exactly the providers that declared it.

    Conversely a stateless provider -- one that resolves every flag with a fresh
    request and holds nothing between them -- has a real initialisation to
    verify while having no event stream of its own to declare ``EVENTS`` for.
    Gating on ``EVENTS`` shut it out of a scenario it should be held to.

    Declare it if initialisation actually contacts the backend and its outcome,
    success or failure, is observable to the application.
    """

    EVENTS = "events"
    """Provider emits lifecycle events at all, at minimum ``PROVIDER_READY``."""

    STALE = "stale"
    """Provider enters ``STALE`` and emits ``PROVIDER_STALE`` when it loses its backend."""

    CONFIGURATION_CHANGE = "configuration-change"
    """Provider detects configuration changes and emits ``PROVIDER_CONFIGURATION_CHANGED``."""

    OBJECT = "object"
    """Provider supports structured (object) flag values."""

    VARIANTS = "variants"
    """Provider names the variant it resolved.

    Gated because a variant is optional rather than required. `Requirement 2.2.4
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    is a **SHOULD** -- in normal execution a provider "SHOULD populate the
    resolution details structure's variant field" -- and ``types.md`` types the
    field ``variant (string, optional)``. The same section adds that the value
    "might only be meaningful in the context of the flag management system
    associated with the provider".

    Some backends have no variant concept for a plain flag at all. Their
    evaluation response carries no such key, so the provider never receives one
    and no amount of seeding can produce one. Asserting a variant in every
    evaluation scenario failed such a backend ten times over for something that
    is not a defect and that no provider author can fix -- and left nothing to
    record as a :class:`~.config.KnownDeviation`, because there was no
    capability to hang one on.

    Declaring it runs one Scenario Outline that asserts the variant for each of
    the eight flags whose variant name the canonical set fixes. Withholding it
    skips those rows with the reason and changes nothing else: the value
    assertions live in untagged scenarios, because
    `Requirement 2.2.3
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    makes the value a **MUST**.
    """

    DISABLED_FLAGS = "disabled-flags"
    """Provider resolves a flag disabled in the management system to the code default.

    Gated because it needs two things and only one of them comes for free. The
    caller's default value is held by the provider, which always has it. What
    the provider also needs is a **signal** that the flag was disabled, told
    apart from an ordinary resolution and from a missing flag -- and that is a
    property of the backend and its protocol. One that has no disabled state, or
    that answers ``FLAG_NOT_FOUND`` for a disabled flag, gives the provider
    nothing to act on, and no care in the provider produces a substitution it
    was never told to make.

    Appendix F draws the line somewhere else, and what this suite measured does
    not bear that out. The appendix has it that a provider whose backend decides,
    "such as one speaking OFREP, cannot: the server never sees the caller's
    default, so it has no way to return it". Both halves of that are observably
    not the obstacle. flagd's RPC resolver is a remote evaluator by exactly that
    description and satisfies the capability: the server answers reason
    ``DISABLED`` with no variant and no value, and the resolver substitutes the
    caller's default locally on the strength of that signal
    (``resolvers/grpc.py``). flagd's OFREP endpoint answers the same flag with
    ``{"reason": "DISABLED"}`` and no ``value`` and no ``variant`` -- the same
    signal in another envelope -- and the Python OFREP provider already falls
    back to the caller's default for the absent value. It fails these scenarios
    for a reason unrelated to architecture, which its own suite records.

    So the tag is worth gating, but for the reason above rather than the one the
    appendix gives, and that discrepancy belongs upstream rather than papered
    over here. What it changes locally is only what a withheld declaration may be
    read as: not necessarily an impossibility, so a reader has to look at the
    adoption's own note for which it was.

    Withholding it still needs no :class:`~.config.KnownDeviation`, for the
    reason every gated capability does -- a deviation records a gap in behaviour
    the provider is *required* to have, and this one is optional. That holds
    whether the gap is architectural or a defect; where it is a defect, the
    adoption's note is where to say so.

    Nothing in the specification says what a provider owes a disabled flag.
    `Requirement 1.4.7
    <https://github.com/open-feature/spec/blob/main/specification/sections/01-flag-evaluation.md>`_
    is about the SDK propagating whatever reason arrived, and `Requirement 2.2.5
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    only lists ``DISABLED`` among the reason strings a provider **may** use. So
    Appendix F states the behaviour, the way it does for
    :attr:`NUMERIC_COERCION`, and gates it.

    Declaring it runs one Scenario Outline of four rows, over the four
    ``disabled-*`` flags the canonical set added at spec revision ``009afe06``.
    They mirror ``boolean-flag``, ``string-flag``, ``integer-flag`` and
    ``float-flag`` exactly, differing only in ``state``, and each row's caller
    default differs from the flag's configured value -- so a provider that
    ignores the state returns the configured value and is caught on the value
    alone, which rests on 2.2.3, a **MUST**.

    The rows assert the value and the absence of an error, and deliberately
    **not** the reason: pinning ``DISABLED`` here would rest on 2.2.5, a
    **SHOULD** that permits "some other string". It is pinned in
    ``reason.feature`` instead, which composes this tag with
    :attr:`STANDARD_REASONS` so that both must be declared before the reason is
    asserted. No variant is asserted either, because a
    disabled flag has resolved no variant and there is none to name -- so this
    capability and :attr:`VARIANTS` do not compose, which is why the rows are not
    part of the variant outline.

    The SDK's own ``InMemoryProvider`` cannot declare this, and the reason is
    worth knowing before adopting it as a reference: ``InMemoryFlag`` accepts a
    ``state`` of ``DISABLED`` and nothing ever reads it, so a disabled flag is
    served like any other. ``_decode_canonical_flags`` passes the state through
    faithfully; the provider is where it stops.
    """

    UNAVAILABLE_INIT = "unavailable"
    """Provider reports an error state promptly against a backend it cannot reach."""

    NUMERIC_COERCION = "numeric-coercion"
    """Provider coerces between integer and float only when lossless, else ``TYPE_MISMATCH``.

    This is the one entry here that **the specification does not define**.
    OpenFeature has a single numeric type on purpose -- ``number`` is "a numeric
    value of unspecified type or size", and languages *may* differentiate between
    integers and floats "as idioms dictate" -- so no requirement says what a
    provider must do when a value does not fit the accessor it was asked through.
    That gap is `open-feature/spec#430
    <https://github.com/open-feature/spec/issues/430>`_.

    The rule this capability is tested against is therefore **borrowed, not
    normative**: lossless coercion is permitted, lossy coercion must fail. An
    integral float such as ``10.0`` requested as an integer must succeed; ``0.5``
    must not. It comes from flagd's `numeric coercion ADR
    <https://github.com/open-feature/flagd/blob/main/docs/architecture-decisions/numeric-coercion.md>`_,
    which is scoped to flagd's own implementations, and the tag carries that name
    -- it was ``@strict-numeric-typing`` -- because two vocabularies for one
    observable property is worse than one borrowed name.

    **A provider that behaves differently is not violating the specification.**
    So this is genuinely optional, rather than optional as a concession to a
    defect: withholding it may be a deliberate choice as readily as a known bug.
    Where it is a bug, say so -- a report's ``knownDeviations`` is for exactly
    that, and flagd's instance is tracked as `open-feature/flagd#1996
    <https://github.com/open-feature/flagd/issues/1996>`_.

    Both halves have scenarios, and a provider declaring the tag must satisfy
    all three. The lossy half asks for ``float-flag`` (``0.5``) as an integer
    and expects ``TYPE_MISMATCH``; the lossless half asks for
    ``integral-float-flag`` (``10.0``) as an integer and for ``integer-flag``
    (``10``) as a float, and expects both to succeed. Rejecting every float is
    an easy way to pass the first, and the other two are what stop it.

    The SDK's own ``InMemoryProvider`` cannot declare this: it hands values
    back untouched and the client's type check is ``isinstance``-based, so
    ``10.0`` requested as an integer is a ``TYPE_MISMATCH`` rather than ``10``.
    That is the provider declining to coerce, not the language refusing to ask:
    a provider that does coerce returns an ``int`` and the same check passes it.
    In a language with one numeric type the question could not be put at all,
    which is why Appendix F names this as inexpressible there and why
    :data:`INEXPRESSIBLE_CAPABILITIES` is empty here. The width of the integer
    accessor is a separate property, and a separate capability:
    :attr:`LARGE_INTEGERS`.
    """

    LARGE_INTEGERS = "large-integers"
    """Provider resolves integers up to 2^53 - 1 exactly.

    A property of the language's SDK as much as of the provider, which is why
    it is a capability rather than mandatory: Java's integer accessor is a
    32-bit ``Integer``, and a provider cannot resolve a value the accessor has
    no room for. Every language can ask for 2^31 - 1, so that precision
    scenario is untagged; only the one asking for 2^53 - 1 carries this tag.

    Python's ``int`` is unbounded, so a Python provider declares it unless
    something of its own -- a 32-bit field in its wire format, a float on the
    way through -- narrows the value. Which makes this one of the two
    capabilities Appendix F names as inexpressible somewhere and **not** here:
    :data:`INEXPRESSIBLE_CAPABILITIES` is empty in Python, and says on what
    measurement. Nothing above 2^53 - 1 is asked for:
    JavaScript cannot represent it, and what a provider owes a value that does
    not fit the requested accessor is the open question in
    `open-feature/spec#430 <https://github.com/open-feature/spec/issues/430>`_.
    """

    REINITIALIZATION = "reinitialization"
    """Provider can be initialised again after ``shutdown``, and serves flags afterwards.

    Gated rather than mandatory because the specification permits reuse without
    requiring it. `Requirement 2.5.2
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    says a provider **SHOULD** revert to its uninitialized state after
    ``shutdown``, and its supporting text adds that "some providers **may**
    allow reinitialization from this state". A provider that releases its client
    on shutdown and declines to be started again is exercising a choice the
    specification offers it, not exhibiting a defect -- so withholding this
    capability needs no :class:`~.config.KnownDeviation` entry.

    The scenario was untagged until spec revision ``fc99d5ac``, on the reading
    that reverting to the uninitialized state is observable as exactly one thing
    -- being initialisable again. That inference does not hold, and asserting it
    unconditionally reported a permitted choice as a conformance failure. A false
    failure is the mirror image of a vacuous pass.

    Reverting the state is not separately observable either: a provider that
    reverts but refuses reuse presents identically to one that did neither. So
    the gated reuse scenario is the only assertion the requirement admits, and it
    is worth keeping for the providers that do offer reuse -- releasing the client
    on shutdown while leaving an initialised flag set behind is easy to write,
    and leaves the provider evaluating against a closed connection rather than
    failing outright.

    **This tag narrows :attr:`LIFECYCLE` rather than standing beside it.** The
    scenario lives in ``lifecycle.feature``, which carries ``@lifecycle`` at the
    feature level, so the scenario inherits that tag and carries both. The gate
    skips a scenario if *any* capability gating it is undeclared, so reuse is
    exercised only by an adoption declaring :attr:`LIFECYCLE` **and** this --
    declaring this one alone leaves the scenario skipped on ``@lifecycle``, and
    the declaration unverified. Which is the trap worth naming: a provider that
    withholds ``LIFECYCLE`` never ran this scenario, at this pin or the one
    before it, so nothing about its behaviour on reuse has been observed either
    way and there is no evidence on which to declare this.
    """

    TARGETING = "targeting"
    """Provider resolves a flag differently for a matching evaluation context.

    Reserved and undeclarable until spec revision ``26362f85``, on the reading
    that targeting is backend evaluation logic and therefore out of scope. The
    scope argument still holds -- what the three scenarios test is not how a
    backend evaluates a rule -- but the conclusion did not: they exist to show
    that the **context reached the backend at all**, which is a property of the
    provider and of nothing else.

    ``targeting-key-flag`` is the one flag in the canonical set with a rule, and
    it is what makes passthrough observable without an echo endpoint on the
    control API: a matching context resolves ``hit`` where anything else
    resolves ``miss``, so a provider that drops the context on the floor is
    caught by the resolved value itself. The rule is specified by behaviour
    rather than by syntax -- resolve ``hit`` when the targeting key is exactly
    ``5c3d8535-f81a-4478-a6d3-afaa4d51199e`` -- so a backend expresses it
    however it expresses targeting.

    The three scenarios are the matching context, the non-matching one and no
    context at all. The second and third are not padding: a provider that always
    returned the targeted value would pass the first, and one that refuses to
    evaluate a rule with no targeting key present is caught by the third.

    Two more scenarios carry this tag alongside :attr:`STANDARD_REASONS`, in
    ``reason.feature``, asserting ``TARGETING_MATCH`` for the hit and
    ``DEFAULT`` for the miss. They need both: a provider with no targeting has
    no rule to match, so there is no ``TARGETING_MATCH`` for it to report and
    the scenario would fail it for an absence rather than a defect. Declaring
    this capability alone leaves them skipped, and changes nothing about the
    three above.

    Declare it if the backend under test can express that rule and the provider
    forwards the targeting key. A backend with no targeting at all leaves it
    undeclared and the three scenarios are skipped with the reason -- which is
    also the right answer for an in-memory flag set whose decoder ignores the
    ``targeting`` member, as this package's own does.
    """

    STANDARD_REASONS = "standard-reasons"
    """Provider reports the standard resolution reasons, with the standard meanings.

    **A claim, not an exemption.** `Requirement 2.2.5
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    is a **SHOULD**, and it goes further than 2.2.4 does: it lets a provider
    populate ``reason`` with one of the listed values *"or some other string
    indicating the semantic reason for the returned flag value"*. A provider
    whose backend reports vendor-specific reasons is therefore conformant, and
    asserting an exact reason against it would fail it for something the
    specification permits.

    An earlier revision of the suite did exactly that, in thirteen places across
    ``evaluation.feature``, ``errors.feature`` and ``lifecycle.feature``, and
    Appendix F recorded the narrowing as a deliberate exception. It is not one
    any more. It bought very little -- every canonical flag resolves to a value
    distinct from the caller's default, so a provider that silently falls back
    is already caught by the value assertion, and the reason only said *why* it
    failed -- and of the thirteen, five sat beside an error-code assertion that
    already carries the **MUST**, while the other eight asserted ``STATIC``, the
    one reason the specification genuinely leaves open.

    So the reasons now live in ``reason.feature``, gated as a whole at the
    feature level. Declaring this capability is a provider saying "I use the
    standard vocabulary with the standard meanings", and that file is what
    checks the claim. A provider that does not declare it **loses nothing**: its
    values, variants and error codes are asserted everywhere else, on **MUST**
    requirements. What the declaration adds is something a report's reader can
    act on -- anyone building telemetry, dashboards or debugging on ``reason``
    can see that the vocabulary was verified rather than assumed.

    The meanings are the content of the claim, and they constrain nobody who
    does not make it:

    * ``STATIC`` -- the flag was resolved from configuration and carries no
      targeting rule;
    * ``TARGETING_MATCH`` -- a targeting rule matched the evaluation context;
    * ``DEFAULT`` -- a targeting rule exists and did not match;
    * ``DISABLED`` -- the flag is disabled in the management system;
    * ``ERROR`` -- the evaluation failed, and an error code is reported with it.

    ``STATIC`` for the first row is the call worth flagging. ``types.md`` types
    ``DEFAULT`` as *"no dynamic evaluation occurred **or** dynamic evaluation
    yielded no result"*, which a rule-less flag satisfies as readily as
    ``STATIC`` does -- two providers can disagree here and both conform. A
    provider that answers ``DEFAULT`` for a rule-less flag is not defective; it
    does not use the standard meanings, and should not declare the tag.

    ``ERROR`` is the row where the suite's subject is blurred, and it is
    asserted anyway. The other four rest on `Requirement 1.4.7
    <https://github.com/open-feature/spec/blob/main/specification/sections/01-flag-evaluation.md>`_,
    which makes the SDK propagate the provider's reason -- but only *"in cases of
    normal execution"*. Abnormal execution is 1.4.9, a **SHOULD** on the *SDK* to
    "indicate an error", and nothing requires the provider's reason to survive.
    So a passing ``ERROR`` scenario establishes that what reached the
    application is coherent, not that the provider produced it. It is still
    worth asserting, because the pair is what carries the meaning: the error
    code alone is already covered for every provider by ``errors.feature``,
    ungated and on a **MUST**, and the reason alone could have been written by
    the SDK. An evaluation reporting ``FLAG_NOT_FOUND`` with reason ``STATIC``
    is incoherent whoever wrote it.

    ``SPLIT``, ``UNKNOWN``, ``CACHED`` and ``STALE`` are not asserted. The first
    two have no scenario that produces them; ``CACHED`` needs a repeat
    evaluation, which nothing here performs without a configuration change in
    between, and belongs behind the reserved :attr:`CACHING`; ``STALE`` needs a
    scenario asserting what a provider serves *during* an outage, which is the
    same gap.

    **Tags compose, and here that is load-bearing.** ``TARGETING_MATCH`` cannot
    be observed without targeting and ``DISABLED`` cannot be observed unless the
    backend distinguishes a disabled flag, so those scenarios carry
    :attr:`TARGETING` and :attr:`DISABLED_FLAGS` as well. A provider declaring
    this capability alone runs the four ``STATIC`` rows and the two error
    scenarios, and skips the other three with their reason.

    This is also the first capability whose tag is carried at the **feature**
    level rather than on each scenario. pytest-bdd marks a scenario from
    ``scenario.tags | feature.tags | rule.tags``, so the gate -- which reads
    markers -- sees it on every scenario in the file, and ``Scenario.tags``
    alone would not have.
    """

    CACHING = "caching"
    """Reserved, and **not declarable**. No scenario carries this tag yet."""

    @property
    def tag(self) -> str:
        """Return the Gherkin tag, with its leading at-sign, that gates this capability."""
        return f"@{self.value}"

    @property
    def reserved(self) -> bool:
        """Whether this capability exists in the vocabulary but gates no scenario."""
        return self in RESERVED_CAPABILITIES

    @property
    def inexpressible(self) -> bool:
        """Whether this SDK cannot put the question this capability's scenarios ask.

        Distinct from :attr:`reserved` in every respect except that both end in a
        refusal. See :data:`INEXPRESSIBLE_CAPABILITIES`.
        """
        return self in INEXPRESSIBLE_CAPABILITIES

    @property
    def inexpressible_reason(self) -> str | None:
        """Which property of this SDK puts the question out of reach, or ``None``.

        The property, not the rule: a message that only says "this cannot be
        declared" leaves the adopter to discover why, and the why is the part
        they could not have been expected to know.
        """
        return INEXPRESSIBLE_CAPABILITIES.get(self)

    def __str__(self) -> str:
        return self.tag


RESERVED_CAPABILITIES: frozenset[Capability] = frozenset({Capability.CACHING})
"""Capabilities that exist in the vocabulary and gate no scenario.

They are documented so the vocabulary has a place for them when scenarios exist,
and until then they **must not be declared** and must not appear in a conformance
report's declaration. Nothing carries the tag, so declaring it cannot be
verified, cannot produce a skip, and tells a reader of the report only that
something was claimed and nothing examined.

Listed once, here, and read everywhere else -- by
:data:`DECLARABLE_CAPABILITIES`, by :attr:`Capability.reserved` and by the
validation in :class:`~.config.TckConfig` -- so that the set and the rule cannot
drift apart.

``@caching`` is the only one left. :attr:`Capability.TARGETING` was here until
spec revision ``26362f85`` gave it scenarios, and leaving a tag reserved once it
has them would be the mirror of the mistake this set exists to prevent: a
capability that *can* be verified and is refused the chance.
"""

INEXPRESSIBLE_CAPABILITIES: Mapping[Capability, str] = MappingProxyType({})
"""Capabilities this language's SDK cannot put the question for, and why.

**Empty in Python, and that is a measurement rather than an omission.** The two
that exist anywhere are :attr:`Capability.LARGE_INTEGERS`, inexpressible where
the integer accessor is a 32-bit ``Integer``, and
:attr:`Capability.NUMERIC_COERCION`, inexpressible where the language has a
single numeric type and "a float requested as an integer" does not name two
different requests. Python has neither property: ``int`` is arbitrary-precision,
and ``get_integer_details`` and ``get_float_details`` are separate accessors
reaching separate provider methods, type-checked against ``int`` and ``float``
separately. Both were checked by asking all four questions through the SDK
rather than by reading its source, and every one of them was answered.

So this mapping carries no entries, and the machinery around it carries no load
here. It exists anyway because the rule is Appendix F's rather than this
package's, because the next capability may hit it, and because the cost of the
two is not symmetric: an unused mechanism is a few lines nobody reads, while a
missing one is discovered by an adopter publishing a claim no scenario could
have examined.

**Not the same thing as a reservation, and the difference is what the two
messages have to carry.** A reserved capability is global and temporary -- no
scenario anywhere carries the tag, and the reservation expires the moment the
specification writes one. An inexpressible capability is one language's and
permanent: the scenarios exist, other languages run them and pass them, and
nothing changes until the SDK does. A reader seeing a capability missing from a
report has to be able to tell *"this provider declined"* from *"no provider in
this language can be asked"*, because only the first says anything about the
provider. Hence a mapping rather than a set: the value is the property of the
SDK that puts the question out of reach, and it is the half of the message an
adopter could not have worked out for themselves.

A capability belongs here only when **no** provider in this language could ever
satisfy it. A provider that gets the answer wrong is a different thing entirely
and belongs nowhere near this mapping. flagd's two Python resolvers answer the
three ``@numeric-coercion`` scenarios differently from each other: in-process
refuses ``0.5`` as an integer and widens ``10`` to a float, while RPC widens
``10`` and silently narrows ``0.5`` to ``0``. Each is a defect in an
implementation, recorded where that adoption records its defects, and
withholding the tag is the honest report for both. Listing it here would say the
question cannot be asked -- and two resolvers of one provider giving different
answers to it is the proof that it can.

Never overlaps :data:`RESERVED_CAPABILITIES`: a tag no scenario carries is
reserved, whatever any SDK could express about it.
"""

DECLARABLE_CAPABILITIES: frozenset[Capability] = (
    frozenset(Capability)
    - RESERVED_CAPABILITIES
    - frozenset(INEXPRESSIBLE_CAPABILITIES)
)
"""Every capability an adoption may declare: the vocabulary minus what is refused.

A reasonable starting point for a new adoption: declare everything, run the
suite, and remove only what the provider genuinely cannot do. Narrowing from this
set surfaces gaps; widening towards it hides them.

It excludes the reserved capabilities rather than spanning the whole enum, and it
is named for what it is rather than for "all", because the declare-everything
convenience is exactly how a reserved tag reaches a report by accident: an
adopter writing "every capability except X" picks up every reserved tag on the
way past, which is how one implementation came to report ``@targeting`` and
``@caching`` as declared without anyone deciding to claim them -- back when both
were reserved.

It excludes :data:`INEXPRESSIBLE_CAPABILITIES` for the same reason and one more:
that set is empty in Python, so a default spanning the whole enum would look
correct here forever and be wrong the day an entry is added, in the one language
where it was added. Derived rather than listed, so it cannot be the thing that is
out of date.
"""

_BY_MARKER: dict[str, Capability] = {c.value: c for c in Capability}
_BY_TAG: dict[str, Capability] = {c.tag: c for c in Capability}


def capability_for_marker(name: str) -> Capability | None:
    """Map a pytest marker name onto the capability it gates, if any.

    A marker that does not name a capability gates nothing, which is what lets
    the canonical feature files carry organisational tags freely.
    """
    return _BY_MARKER.get(name)


def capability_for_tag(tag: str) -> Capability | None:
    """Map a Gherkin tag, leading at-sign included, onto the capability it gates.

    The tag form rather than the marker form because that is what the
    conformance report carries: the report records a scenario's tags as the
    feature files spell them, and deciding whether a failure counts against a
    capability means reading them back.
    """
    return _BY_TAG.get(tag)


def expired_reservations(tags: typing.Iterable[str]) -> tuple[Capability, ...]:
    """Reserved capabilities that the tags handed in turn out to carry.

    A non-empty answer means some scenario is both unrunnable and unclaimable.
    Declaring a reserved capability is refused, so the capability gate skips
    every scenario carrying its tag, and the report says a gap exists where the
    provider may well have none. Appendix F names that the unclaimable
    capability, and it is the quieter mirror of declaring a capability nothing
    verifies: nobody can claim the tag, so nothing else about the run changes.

    Two things put a reserved tag on a scenario and this reports only that one
    of them happened. Either :data:`RESERVED_CAPABILITIES` is out of date --
    the scenarios the tag was held open for now exist, so the capability can be
    verified and an adoption should be allowed, and required, to say whether it
    has it -- or an adopter has used a reserved name for a tag of their own.
    Telling the two apart is the caller's, because the caller is what knows
    where the tags came from: the remedies differ and the consequence does not.

    Compared against tags rather than against a second list, because a
    reservation expires in the specification repository while this set lives
    here. Deduplicated and ordered by tag: the tags arrive from every scenario
    of every feature file, and one carried twice is not two expiries.
    """
    carried = set(tags)
    expired = (c for c in RESERVED_CAPABILITIES if c.tag in carried)
    return tuple(sorted(expired, key=lambda capability: capability.tag))
