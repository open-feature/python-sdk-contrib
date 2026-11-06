"""Optional parts of the provider contract, and the Gherkin tags that gate them."""

from __future__ import annotations

import typing
from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType

__all__ = ["Capability"]


class Capability(str, Enum):
    """An optional part of the OpenFeature provider contract.

    Not every provider implements every part of the specification, so each
    declares what it supports through :attr:`TckConfig.capabilities`.

    Every capability corresponds to exactly one Gherkin tag. pytest-bdd turns
    those tags into pytest markers, and a scenario carrying a marker whose
    capability was not declared is skipped with the reason reported -- never
    passed. Scenarios with no capability tag are mandatory and always run.

    Two kinds of capability are refused rather than declared:
    :data:`RESERVED_CAPABILITIES`, which no scenario carries yet, and
    :data:`INEXPRESSIBLE_CAPABILITIES`, whose question this language's SDK
    cannot put at all. :data:`DECLARABLE_CAPABILITIES` is what is left.

    `Appendix F
    <https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md>`_
    owns the vocabulary and the rules for declaring: what a declaration means,
    when to withhold one, and when a :class:`~.config.KnownDeviation` belongs
    beside it.
    """

    LIFECYCLE = "lifecycle"
    """Provider reaches its backend during initialisation, observably and promptly.

    Declare it if initialisation actually contacts the backend and its outcome,
    success or failure, is observable to the application.
    """

    EVENTS = "events"
    """Provider emits lifecycle events at all, at minimum ``PROVIDER_READY``."""

    STALE = "stale"
    """Provider enters ``STALE`` and emits ``PROVIDER_STALE`` when it loses its backend."""

    CONFIGURATION_CHANGE = "configuration-change"
    """Provider detects configuration changes and emits ``PROVIDER_CONFIGURATION_CHANGED``.

    Declare it if something watches the backend. A provider whose every
    evaluation is an independent request has nothing watching and so nothing to
    notice, and withholding is then the honest report rather than a defect.
    """

    OBJECT = "object"
    """Provider supports structured (object) flag values."""

    VARIANTS = "variants"
    """Provider names the variant it resolved.

    Declare it if the backend has a variant concept for a plain flag. The value
    assertions live in untagged scenarios, so withholding this skips only the
    variant assertions.
    """

    DISABLED_FLAGS = "disabled-flags"
    """Provider resolves a flag disabled in the management system to the code default.

    Declare it if the backend gives the provider a *signal* that the flag was
    disabled, told apart from an ordinary resolution and from a missing flag.

    Composes with :attr:`STANDARD_REASONS` in ``reason.feature``, where the
    reason is pinned; the scenarios here assert the value alone. Does not compose
    with :attr:`VARIANTS`, a disabled flag having resolved no variant.
    """

    UNAVAILABLE_INIT = "unavailable"
    """Provider reports an error state promptly against a backend it cannot reach."""

    NUMERIC_COERCION = "numeric-coercion"
    """Provider coerces between integer and float only when lossless, else ``TYPE_MISMATCH``.

    The rule is flagd's `numeric coercion ADR
    <https://github.com/open-feature/flagd/blob/main/docs/architecture-decisions/numeric-coercion.md>`_
    while `open-feature/spec#430
    <https://github.com/open-feature/spec/issues/430>`_ is open, so a provider
    that behaves differently is not violating the specification.

    Declare it if the provider attempts the coercion at all: one that attempts it
    and gets a direction wrong declares the tag and records a
    :class:`~.config.KnownDeviation`. The width of the integer accessor is a
    separate capability, :attr:`LARGE_INTEGERS`.
    """

    STRING_TYPING = "string-typing"
    """Provider reports ``TYPE_MISMATCH`` for a boolean or integer flag asked as a string.

    Withhold it if the backend stores flag values as strings, which satisfies the
    string accessor for every flag and leaves no mismatch to report.
    **Withholding is not non-conformance**, so it needs no
    :class:`~.config.KnownDeviation` beside it.

    The float and structured cases are behind :attr:`FULLY_TYPED_VALUES` as well,
    so declaring this alone leaves them skipped.
    """

    FULLY_TYPED_VALUES = "fully-typed-values"
    """Backend records a native type for float and structured values too.

    Narrows :attr:`STRING_TYPING` rather than standing beside it: every scenario
    carrying this tag carries that one as well, so declaring this alone runs
    nothing. Withholding it says "this backend keeps floats, or structures, as
    text", and like :attr:`STRING_TYPING` it needs no
    :class:`~.config.KnownDeviation`.
    """

    LARGE_INTEGERS = "large-integers"
    """Provider resolves integers up to 2^53 - 1 exactly.

    A property of the language's SDK as much as of the provider: a 32-bit integer
    accessor has no room for the value, and every language can ask for 2^31 - 1,
    so that precision scenario is untagged. Python's ``int`` is unbounded, so a
    Python provider declares it unless something of its own -- a 32-bit field in
    its wire format, a float on the way through -- narrows the value.
    """

    REINITIALIZATION = "reinitialization"
    """Provider can be initialised again after ``shutdown``, and serves flags afterwards.

    Optional under `Requirement 2.5.2
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_,
    so withholding needs no :class:`~.config.KnownDeviation`.

    **Narrows :attr:`LIFECYCLE` rather than standing beside it**, which is the
    trap worth naming: its scenario sits in a feature file carrying
    ``@lifecycle``, and the gate skips a scenario if *any* capability gating it
    is undeclared, so declaring this one alone leaves the declaration unverified.
    """

    TARGETING = "targeting"
    """Provider resolves a flag differently for a matching evaluation context.

    What the scenarios test is not how a backend evaluates a rule but that the
    **context reached the backend at all**.

    Declare it if the backend under test can express the canonical set's one
    targeting rule and the provider forwards the targeting key -- which an
    in-memory flag set whose decoder ignores the ``targeting`` member, as this
    package's own does, cannot. Also composes with :attr:`STANDARD_REASONS`.
    """

    STANDARD_REASONS = "standard-reasons"
    """Provider reports the standard resolution reasons, with the standard meanings.

    **A claim, not an exemption.** `Requirement 2.2.5
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    lets a provider populate ``reason`` with some other string, so one whose
    backend reports vendor-specific reasons is conformant and loses nothing by
    withholding this. Appendix F's ``@standard-reasons`` section fixes the
    meanings.

    Composes with :attr:`TARGETING` and :attr:`DISABLED_FLAGS`, whose reasons
    cannot be observed without them.

    Carried at the **feature** level rather than on each scenario. pytest-bdd
    marks a scenario from ``scenario.tags | feature.tags | rule.tags``, so the
    gate -- which reads markers -- sees it on every scenario in the file, where
    ``Scenario.tags`` alone would not have.
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

        See :data:`INEXPRESSIBLE_CAPABILITIES`.
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
and until then they **must not be declared** -- nothing carries the tag, so
declaring it cannot be verified and cannot produce a skip.

Listed once, here, and read everywhere else, so that the set and the rule cannot
drift apart. A reservation expires in the specification repository rather than
here, which is what :func:`expired_reservations` exists to notice.
"""

INEXPRESSIBLE_CAPABILITIES: Mapping[Capability, str] = MappingProxyType({})
"""Capabilities this language's SDK cannot put the question for, and why.

**Empty in Python, and that is a measurement rather than an omission.** Each
question was asked through the SDK and answered: ``int`` is arbitrary-precision,
and ``get_integer_details`` and ``get_float_details`` are separate accessors
reaching separate provider methods, type-checked separately.

A mapping rather than a set, because a reader seeing a capability missing from a
report has to be able to tell *"this provider declined"* from *"no provider in
this language can be asked"*. The value is the property of the SDK that puts the
question out of reach.

A capability belongs here only when **no** provider in this language could ever
satisfy it. One that gets the answer wrong belongs in a
:class:`~.config.KnownDeviation` beside a declared capability instead.

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

Derived rather than listed, and named for what it is rather than for "all",
because a declare-everything convenience is how a reserved or inexpressible tag
reaches a report by accident.
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
    conformance report carries.
    """
    return _BY_TAG.get(tag)


def expired_reservations(tags: typing.Iterable[str]) -> tuple[Capability, ...]:
    """Reserved capabilities that the tags handed in turn out to carry.

    A non-empty answer means some scenario is both unrunnable and unclaimable:
    declaring a reserved capability is refused, so the gate skips every scenario
    carrying its tag, and the report says a gap exists where the provider may
    well have none.

    Either :data:`RESERVED_CAPABILITIES` is out of date, or an adopter has used a
    reserved name for a tag of their own. Telling the two apart is the caller's,
    because the caller is what knows where the tags came from.

    Deduplicated and ordered by tag.
    """
    carried = set(tags)
    expired = (c for c in RESERVED_CAPABILITIES if c.tag in carried)
    return tuple(sorted(expired, key=lambda capability: capability.tag))


def unknown_capabilities(tags: typing.Iterable[str]) -> tuple[str, ...]:
    """Tags handed in that this vocabulary cannot resolve to a capability.

    :func:`expired_reservations` run in the other direction. **An unknown tag
    gates nothing, so its scenarios stay mandatory for every adopter**: a suite
    that has not learned a new capability goes on demanding the old behaviour,
    and a provider that legitimately withholds it shows unexplained failures
    while every other provider stays green. Appendix F makes failing the run over
    it a **MUST**.

    Returns the tags rather than anything richer, because by definition there is
    no capability to return. Deduplicated and sorted.

    Takes tags rather than reading them itself because a tag that names no
    capability is a problem only where every tag is meant to be a capability --
    the canonical assets -- and is ordinary in an adopter's own feature files.
    """
    return tuple(sorted({tag for tag in tags if capability_for_tag(tag) is None}))
