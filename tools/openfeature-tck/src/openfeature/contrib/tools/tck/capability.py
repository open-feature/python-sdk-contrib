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

    `Appendix F
    <https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md>`_
    owns the vocabulary and the rules for declaring, including what a
    declaration means, when to withhold one and when a
    :class:`~.config.KnownDeviation` belongs beside it. The docstrings here say
    what each tag gates *in this implementation* -- which scenarios run, what a
    withholding skips, and what Python's SDK makes of the question -- and link
    rather than restate.

    Every capability corresponds to exactly one Gherkin tag. pytest-bdd turns
    those tags into pytest markers, and a scenario carrying a marker whose
    capability was not declared is skipped with the reason reported -- never
    passed. Scenarios with no capability tag are mandatory and always run.

    Two kinds of capability are refused rather than declared, and they are
    refused for different reasons and with different messages:
    :data:`RESERVED_CAPABILITIES`, which no scenario anywhere carries yet, and
    :data:`INEXPRESSIBLE_CAPABILITIES`, whose question this language's SDK cannot
    put at all. :data:`DECLARABLE_CAPABILITIES` is what is left.
    """

    LIFECYCLE = "lifecycle"
    """Provider reaches its backend during initialisation, observably and promptly.

    Deliberately separate from :attr:`EVENTS`, because the two are independent in
    both directions: an SDK dispatches ``PROVIDER_READY`` around ``initialize``
    for *any* provider, so gating the readiness scenario on ``EVENTS`` made it
    vacuous for exactly the providers that declared it, while a stateless
    provider has a real initialisation to verify and no event stream of its own.

    Declare it if initialisation actually contacts the backend and its outcome,
    success or failure, is observable to the application.
    """

    EVENTS = "events"
    """Provider emits lifecycle events at all, at minimum ``PROVIDER_READY``."""

    STALE = "stale"
    """Provider enters ``STALE`` and emits ``PROVIDER_STALE`` when it loses its backend."""

    CONFIGURATION_CHANGE = "configuration-change"
    """Provider detects configuration changes and emits ``PROVIDER_CONFIGURATION_CHANGED``.

    **The worked example of one skip meaning two different things**, which is
    why it is spelled out on this tag rather than left abstract. Both of this
    repository's withholdings of it are real and neither is the other:

    * **A choice.** The OFREP adoption withholds it because every evaluation is
      an independent HTTP request: nothing is watching the backend, so there is
      nothing to notice. A provider built that way is not defective, and a
      :class:`~.config.KnownDeviation` there would assert a defect that does not
      exist.
    * **A defect.** The in-memory self-test withholds it because the SDK's
      ``InMemoryProvider`` copies its flag mapping in the constructor and exposes
      no way to change it, where `Appendix A
      <https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md>`_
      **requires** an SDK's in-memory provider to support updating the flag set
      and emitting this event. Tracked as `open-feature/python-sdk#620
      <https://github.com/open-feature/python-sdk/issues/620>`_.

    A report shows the same absence in both cases, which is the whole reason the
    declaration is not the last word: the adoption's note says which, and for the
    second kind there is a ``ControllableInMemoryProvider`` here supplying what
    the SDK lacks, so the scenarios still run somewhere.
    """

    OBJECT = "object"
    """Provider supports structured (object) flag values."""

    VARIANTS = "variants"
    """Provider names the variant it resolved.

    Gated because a variant is optional rather than required: `Requirement 2.2.4
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    is a **SHOULD** and ``types.md`` types the field ``variant (string,
    optional)``, so a backend with no variant concept for a plain flag never
    gives the provider one to report.

    Declaring it runs one Scenario Outline that asserts the variant for each of
    the eight flags whose variant name the canonical set fixes. Withholding it
    skips those rows with the reason and changes nothing else: the value
    assertions live in untagged scenarios, because `Requirement 2.2.3
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

    Nothing in the specification says what a provider owes a disabled flag.
    `Requirement 1.4.7
    <https://github.com/open-feature/spec/blob/main/specification/sections/01-flag-evaluation.md>`_
    is about the SDK propagating whatever reason arrived, and `Requirement 2.2.5
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    only lists ``DISABLED`` among the reason strings a provider **may** use. So
    Appendix F states the behaviour, the way it does for
    :attr:`NUMERIC_COERCION`, and gates it.

    A remote evaluator is not shut out of this, which is worth knowing before
    reading a withholding as an architectural impossibility: flagd's RPC resolver
    satisfies the capability by substituting locally on the strength of the
    server's ``DISABLED`` reason, and flagd's OFREP endpoint sends the same
    signal in another envelope. The two adoptions in this repository record what
    each one does with it.

    Declaring it runs one Scenario Outline of four rows, over the four
    ``disabled-*`` flags of the canonical set. They mirror ``boolean-flag``,
    ``string-flag``, ``integer-flag`` and ``float-flag`` exactly, differing only
    in ``state``, and each row's caller default differs from the flag's
    configured value -- so a provider that ignores the state returns the
    configured value and is caught on the value alone, which rests on 2.2.3, a
    **MUST**.

    The rows assert the value and the absence of an error, and deliberately
    **not** the reason: pinning ``DISABLED`` here would rest on 2.2.5, a
    **SHOULD** that permits "some other string". It is pinned in
    ``reason.feature`` instead, which composes this tag with
    :attr:`STANDARD_REASONS` so that both must be declared before the reason is
    asserted. No variant is asserted either, because a disabled flag has resolved
    no variant and there is none to name -- so this capability and
    :attr:`VARIANTS` do not compose, which is why the rows are not part of the
    variant outline.

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

    This is the one entry here that **the specification does not define**: the
    rule is borrowed from flagd's `numeric coercion ADR
    <https://github.com/open-feature/flagd/blob/main/docs/architecture-decisions/numeric-coercion.md>`_
    while `open-feature/spec#430 <https://github.com/open-feature/spec/issues/430>`_
    is open, so **a provider that behaves differently is not violating the
    specification**. Appendix F's numeric-coercion note carries the rule, and
    settles which of "declares and fails" and "withholds" a provider reaches for:
    one that *attempts* the coercion and gets a direction wrong declares the
    capability and records a :class:`~.config.KnownDeviation` beside the failing
    scenario, and withholding is for one that cannot attempt the behaviour at
    all.

    Both halves have scenarios, and a provider declaring the tag must satisfy all
    three: the lossy half asks for ``float-flag`` (``0.5``) as an integer and
    expects ``TYPE_MISMATCH``; the lossless half asks for ``integral-float-flag``
    (``10.0``) as an integer and for ``integer-flag`` (``10``) as a float, and
    expects both to succeed. Rejecting every float is an easy way to pass the
    first, and the other two are what stop it.

    The SDK's own ``InMemoryProvider`` is the withholding kind: it hands values
    back untouched and the client's type check is ``isinstance``-based, so
    ``10.0`` requested as an integer is a ``TYPE_MISMATCH`` rather than ``10``.
    That is the provider declining to coerce, not the language refusing to ask --
    a provider that does coerce returns an ``int`` and the same check passes it,
    which is why :data:`INEXPRESSIBLE_CAPABILITIES` is empty here. The width of
    the integer accessor is a separate property, and a separate capability:
    :attr:`LARGE_INTEGERS`.
    """

    STRING_TYPING = "string-typing"
    """Provider reports ``TYPE_MISMATCH`` for a non-string flag requested as a string.

    The second capability here the specification does not define, and it is
    undefined in a stronger sense than :attr:`NUMERIC_COERCION`: that rule is
    borrowed from an ADR that answers a question the specification left open,
    while this one contradicts nothing because **the specification never says
    what the type of a flag value is**. ``TYPE_MISMATCH`` appears once, as a row
    in the error-code table, and no provider requirement obliges anyone to raise
    it; the only normative statement about value type is `Requirement 1.3.4
    <https://github.com/open-feature/spec/blob/main/specification/sections/01-flag-evaluation.md>`_,
    a **SHOULD**, and on the *client* rather than the provider. Appendix F's
    ``@string-typing`` section carries the reasoning.

    Gated because every value has a string representation, so a backend that
    stores flag values as strings satisfies the string accessor for **every**
    flag and has no mismatch to report -- its flags *are* strings, and
    `Requirement 2.2.3
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    asked it for the resolved flag value, which it returned. **A provider that
    withholds this tag is not thereby non-conformant**, which settles the
    instrument as well as the answer: withholding rather than a
    :class:`~.config.KnownDeviation`, because a deviation records a required
    behaviour the provider lacks and this behaviour is not required.

    Declaring it runs one Scenario Outline of three rows -- ``boolean-flag``,
    ``integer-flag`` and ``float-flag`` each asked for as a string -- and one
    scenario for ``object-flag``, which carries :attr:`OBJECT` as well because a
    provider with no structured values cannot be asked that one at all. All four
    were **mandatory** until spec revision ``d47a66eb``, on the reasoning that
    *"is a string a boolean?"* has no defensible wrong answer. That holds for
    parsing a string into another type, which a provider chooses to do; it does
    not hold for rendering another type as a string, which an untyped backend
    does whether anyone chose it or not.

    Nothing about Python narrows the question, so the four scenarios measure the
    provider rather than the SDK: ``get_string_details`` is its own accessor
    reaching its own provider method, and the client's check is
    ``isinstance(value, str)`` -- a provider handing back ``True`` or ``10`` is a
    ``TYPE_MISMATCH`` without the provider having to notice, and one handing back
    ``"true"`` passes the check and fails the scenario. Hence
    :data:`INEXPRESSIBLE_CAPABILITIES` stays empty.
    """

    LARGE_INTEGERS = "large-integers"
    """Provider resolves integers up to 2^53 - 1 exactly.

    A property of the language's SDK as much as of the provider, which is why it
    is a capability rather than mandatory: a 32-bit integer accessor has no room
    for the value. Every language can ask for 2^31 - 1, so that precision
    scenario is untagged; only the one asking for 2^53 - 1 carries this tag.

    Python's ``int`` is unbounded, so a Python provider declares it unless
    something of its own -- a 32-bit field in its wire format, a float on the way
    through -- narrows the value, or unless the backend under test serves no such
    flag for it to be asked about. Which makes this one of the two capabilities
    Appendix F names as inexpressible somewhere and **not** here:
    :data:`INEXPRESSIBLE_CAPABILITIES` is empty in Python, and says on what
    measurement.
    """

    REINITIALIZATION = "reinitialization"
    """Provider can be initialised again after ``shutdown``, and serves flags afterwards.

    Gated rather than mandatory because `Requirement 2.5.2
    <https://github.com/open-feature/spec/blob/main/specification/sections/02-providers.md>`_
    permits reuse without requiring it: a provider that releases its client on
    shutdown and declines to be started again is exercising a choice the
    specification offers it, so withholding this capability needs no
    :class:`~.config.KnownDeviation` entry.

    **This tag narrows :attr:`LIFECYCLE` rather than standing beside it**, and
    that is the trap worth naming. The scenario lives in ``lifecycle.feature``,
    which carries ``@lifecycle`` at the feature level, and the gate skips a
    scenario if *any* capability gating it is undeclared -- so declaring this one
    alone leaves the scenario skipped and the declaration unverified. A provider
    that withholds ``LIFECYCLE`` has therefore never run this scenario, and has
    no evidence on which to declare this one either way.
    """

    TARGETING = "targeting"
    """Provider resolves a flag differently for a matching evaluation context.

    What the three scenarios test is not how a backend evaluates a rule: they
    exist to show that the **context reached the backend at all**, which is a
    property of the provider and of nothing else. ``targeting-key-flag`` is the
    one flag in the canonical set with a rule, and it is what makes passthrough
    observable without an echo endpoint on the control API -- a matching context
    resolves ``hit`` where anything else resolves ``miss``.

    The three scenarios are the matching context, the non-matching one and no
    context at all. The second and third are not padding: a provider that always
    returned the targeted value would pass the first, and one that refuses to
    evaluate a rule with no targeting key present is caught by the third.

    Two more scenarios carry this tag alongside :attr:`STANDARD_REASONS`, in
    ``reason.feature``, asserting ``TARGETING_MATCH`` for the hit and ``DEFAULT``
    for the miss; declaring this capability alone leaves them skipped and changes
    nothing about the three above.

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
    is a **SHOULD** that lets a provider populate ``reason`` with *"some other
    string indicating the semantic reason for the returned flag value"*, so a
    provider whose backend reports vendor-specific reasons is conformant and is
    not expected to declare this. Declaring it says "I use the standard
    vocabulary with the standard meanings", and ``reason.feature`` is what checks
    the claim; Appendix F's ``@standard-reasons`` section is where the meanings
    are fixed, including the two rows -- ``STATIC`` for a rule-less flag, and
    ``ERROR`` -- that are calls rather than consequences.

    A provider that does not declare it **loses nothing**: its values, variants
    and error codes are asserted everywhere else, on **MUST** requirements.

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
and until then they **must not be declared** -- nothing carries the tag, so
declaring it cannot be verified and cannot produce a skip.

Listed once, here, and read everywhere else -- by
:data:`DECLARABLE_CAPABILITIES`, by :attr:`Capability.reserved` and by the
validation in :class:`~.config.TckConfig` -- so that the set and the rule cannot
drift apart. A reservation expires in the specification repository rather than
here, which is what :func:`expired_reservations` exists to notice.
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

**Not the same thing as a reservation**, and the value is what carries the
difference: a reader seeing a capability missing from a report has to be able to
tell *"this provider declined"* from *"no provider in this language can be
asked"*. Hence a mapping rather than a set -- the value is the property of the
SDK that puts the question out of reach, which is the half of the message an
adopter could not have worked out for themselves.

A capability belongs here only when **no** provider in this language could ever
satisfy it. A provider that gets the answer wrong is a different thing entirely:
flagd's two Python resolvers answer the ``@numeric-coercion`` scenarios
differently from each other, and **both** declare the tag, the one that narrows
carrying the :class:`~.config.KnownDeviation`. Listing it here would say the
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
is named for what it is rather than for "all", because a declare-everything
convenience is exactly how a reserved tag reaches a report by accident -- an
adopter writing "every capability except X" picks up every reserved tag on the
way past.

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

    A non-empty answer means some scenario is both unrunnable and unclaimable:
    declaring a reserved capability is refused, so the gate skips every scenario
    carrying its tag, and the report says a gap exists where the provider may
    well have none.

    Two things put a reserved tag on a scenario and this reports only that one
    of them happened. Either :data:`RESERVED_CAPABILITIES` is out of date --
    the scenarios the tag was held open for now exist, so an adoption should be
    allowed, and required, to say whether it has the capability -- or an adopter
    has used a reserved name for a tag of their own. Telling the two apart is the
    caller's, because the caller is what knows where the tags came from: the
    remedies differ and the consequence does not.

    Compared against tags rather than against a second list, because a
    reservation expires in the specification repository while this set lives
    here. Deduplicated and ordered by tag: the tags arrive from every scenario
    of every feature file, and one carried twice is not two expiries.
    """
    carried = set(tags)
    expired = (c for c in RESERVED_CAPABILITIES if c.tag in carried)
    return tuple(sorted(expired, key=lambda capability: capability.tag))
