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

    STRICT_NUMERIC_TYPING = "strict-numeric-typing"
    """Provider keeps the integer and float types distinct instead of coercing between them.

    Unlike every other entry here this is not an optional feature. The
    specification requires a provider to report ``TYPE_MISMATCH`` when the
    requested type cannot be satisfied, and narrowing ``0.5`` to ``0`` to satisfy
    an integer request loses information silently -- the worst failure mode a
    feature flag has, because the application sees a plausible value and no
    error at all.

    It is a capability only so that a provider with this defect can adopt the
    suite today and see the gap reported as an explicit skip, rather than being
    unable to adopt at all. Not declaring it is an admission of a known bug, not
    a design choice. Declare it as soon as the provider is fixed.
    """

    TARGETING = "targeting"
    """Reserved. No scenario carries this tag: targeting is backend evaluation logic."""

    CACHING = "caching"
    """Reserved; no scenario carries this tag yet."""

    @property
    def tag(self) -> str:
        """Return the Gherkin tag, with its leading at-sign, that gates this capability."""
        return f"@{self.value}"

    def __str__(self) -> str:
        return self.tag


ALL_CAPABILITIES: frozenset[Capability] = frozenset(Capability)
"""Every capability the TCK recognises.

A reasonable starting point for a new adoption: declare everything, run the
suite, and remove only what the provider genuinely cannot do. Narrowing from the
full set surfaces gaps; widening towards it hides them.
"""

_BY_MARKER: dict[str, Capability] = {c.value: c for c in Capability}


def capability_for_marker(name: str) -> Capability | None:
    """Map a pytest marker name onto the capability it gates, if any.

    A marker that does not name a capability gates nothing, which is what lets
    the canonical feature files carry organisational tags freely.
    """
    return _BY_MARKER.get(name)
