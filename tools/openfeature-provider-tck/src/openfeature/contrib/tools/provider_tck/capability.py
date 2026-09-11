"""Optional parts of the provider contract, and the Gherkin tags that gate them."""

from __future__ import annotations

from enum import Enum

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
    skips those rows with the reason and changes nothing else: the value and
    reason assertions live in untagged scenarios, because
    `Requirement 2.2.3
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    makes the value a **MUST**.
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
    The width of the integer accessor is a separate property, and a separate
    capability: :attr:`LARGE_INTEGERS`.
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
    way through -- narrows the value. Nothing above 2^53 - 1 is asked for:
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

    Declare it if the backend under test can express that rule and the provider
    forwards the targeting key. A backend with no targeting at all leaves it
    undeclared and the three scenarios are skipped with the reason -- which is
    also the right answer for an in-memory flag set whose decoder ignores the
    ``targeting`` member, as this package's own does.
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

DECLARABLE_CAPABILITIES: frozenset[Capability] = (
    frozenset(Capability) - RESERVED_CAPABILITIES
)
"""Every capability an adoption may declare: the vocabulary minus the reserved tags.

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
