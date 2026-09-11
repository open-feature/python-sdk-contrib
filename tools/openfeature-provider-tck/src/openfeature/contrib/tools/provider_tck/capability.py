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

    TARGETING = "targeting"
    """Reserved, and **not declarable**. No scenario carries this tag: targeting
    is backend evaluation logic."""

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


RESERVED_CAPABILITIES: frozenset[Capability] = frozenset(
    {Capability.TARGETING, Capability.CACHING}
)
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
``@caching`` as declared without anyone deciding to claim them.
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
