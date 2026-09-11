"""The contract a provider author implements to run the suite."""

from __future__ import annotations

import typing
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field

from openfeature.provider import FeatureProvider

from .capability import DECLARABLE_CAPABILITIES, Capability
from .control import BackendControl

__all__ = ["KnownDeviation", "ProviderFactory", "TckConfig"]

ProviderFactory = Callable[[], FeatureProvider]
"""Creates the provider under test.

A factory rather than a single instance because each scenario gets its own
provider, and because a provider often cannot be configured before the suite
starts -- a container stack's host ports do not exist until it is up.
"""

DEFAULT_EVENT_TIMEOUT = 12.0
DEFAULT_READY_TIMEOUT = 30.0


@dataclass(frozen=True)
class KnownDeviation:
    """A gap the provider is known to have, acknowledged rather than hidden.

    Distinct from an undeclared capability, which is a choice the provider is
    entitled to make: this is a defect against something the specification does
    not treat as optional, with the gap tracked somewhere.

    It changes nothing about how the suite runs. The scenario still fails, and
    the results payload still reports it as failed -- a report that softened a
    failure into a footnote would hide exactly what the acknowledgement exists to
    keep visible. What this adds is the acknowledgement itself, in the envelope,
    so that a consumer can tell a known and tracked gap from a surprise.
    """

    issue: str
    """Where the gap is tracked. A URI, because the schema requires one."""

    summary: str
    """What is wrong, for a person reading a comparison page."""

    capability: Capability | None = None
    """The capability the deviation concerns, when it maps to one.

    Left out for a deviation against a mandatory scenario, which belongs to no
    capability -- which is the common case, since a capability a provider fails
    is usually one it should not have declared.
    """

    def as_json(self) -> dict[str, typing.Any]:
        document: dict[str, typing.Any] = {
            "issue": self.issue,
            "summary": self.summary,
        }
        if self.capability is not None:
            document["capability"] = self.capability.tag
        return document


@dataclass(frozen=True)
class TckConfig:
    """Everything the TCK needs to test one provider.

    An adopting module supplies this through a session-scoped ``tck_config``
    fixture; the TCK owns everything else -- registering the provider, awaiting
    events, resetting the backend between scenarios, tearing down. If you find
    yourself writing test infrastructure, that is a defect in this package
    rather than something for you to work around.
    """

    name: str
    """Identifies the suite in test output, and scopes the OpenFeature domain
    the TCK registers providers under so two suites in the same session do not
    observe each other's providers.

    Use something that reads well in a failure message: ``"flagd-rpc"``,
    ``"in-memory"``.
    """

    control: BackendControl
    """The seam through which the TCK manipulates the backend.

    See :class:`~.control.BackendControl` for which implementation is right for
    your provider. The short version: a provider with a real backend drives it
    over the HTTP control API; a provider with no backend at all may control it
    in-process.
    """

    new_provider: ProviderFactory
    """Creates the provider under test, against a backend that is already
    running and seeded with the canonical flag set. Called once per scenario.

    Return a configured but uninitialised provider; the TCK initialises it.
    """

    new_unavailable_provider: ProviderFactory | None = None
    """Creates a provider pointed at a backend that does not exist.

    Used by the initialisation-failure scenarios, which assert that a provider
    unable to reach its backend settles into ``ERROR`` rather than hanging or
    raising out of registration.

    Point it at a closed port on localhost. Do not point it at the backend under
    test -- that must stay up, and simulated outages belong to :attr:`control`.
    Configure a short connection deadline: the scenario allows a bounded time
    for the error, and a provider with a 30-second connect timeout will not make
    it.

    Required only if :attr:`capabilities` includes
    :attr:`Capability.UNAVAILABLE_INIT`. Leaving both out is the honest
    configuration for a provider with no backend, and those scenarios are then
    skipped with the reason reported.
    """

    capabilities: Collection[Capability] = field(default=DECLARABLE_CAPABILITIES)
    """Which optional parts of the provider contract this provider supports.

    Typed as a ``Collection`` rather than a ``frozenset`` so that the obvious
    thing to write -- a set literal, which is what the README shows -- is also
    the correctly typed thing to write. It is normalised to a frozenset on
    construction, so a list, a set or a generator all behave identically.

    Scenarios tagged with an undeclared capability are reported as skipped with
    the reason, never as passed. Defaults to every *declarable* capability --
    :data:`~.capability.DECLARABLE_CAPABILITIES`, which excludes the reserved
    tags no scenario carries -- and narrowing it surfaces gaps where widening
    towards it hides them.

    Naming a reserved capability here is rejected at construction rather than
    passed into a report. See :data:`~.capability.RESERVED_CAPABILITIES`.

    A capability that cannot hold in a language at all -- ``@numeric-coercion``
    where the language has a single numeric type, ``@large-integers`` on a
    32-bit accessor -- is a property of the SDK rather than of the provider, and
    Appendix F records it once rather than every report restating it. Here it is
    simply left undeclared, and the skip carries the reason.
    """

    known_deviations: Sequence[KnownDeviation] = ()
    """Gaps this provider is known to have, with each one tracked somewhere.

    An acknowledgement, not an excuse: the scenarios still fail and the results
    payload still says so. See :class:`KnownDeviation`.
    """

    event_timeout: float = DEFAULT_EVENT_TIMEOUT
    """Seconds to wait for a provider event.

    The single most important knob for a provider author, because providers
    observe backend changes on wildly different timescales. A streaming provider
    sees a configuration change in milliseconds; one polling every 30 seconds
    may need most of a poll interval. Set it to comfortably exceed your
    worst-case detection latency, or the suite reports timeouts that are really
    just impatience.

    Scenarios can tighten this with the explicit ``within {int}ms`` step, which
    always wins over this value.
    """

    ready_timeout: float = DEFAULT_READY_TIMEOUT
    """Seconds to wait for a provider to reach ``READY`` during initialisation.

    Also the longest the suite waits on a direct ``shutdown`` or ``initialize``
    call before giving up on it and recording the wait as a failure, so that a
    provider whose shutdown hangs on a backend that is gone fails its scenario
    with a message rather than hanging the session.
    """

    def __post_init__(self) -> None:
        problems: list[str] = []

        if not self.name:
            problems.append(
                "name is required: it scopes the OpenFeature domain and identifies "
                "the suite in test output"
            )
        if self.control is None:
            problems.append(
                "control is required: see BackendControl for which implementation "
                "fits your provider"
            )
        if self.new_provider is None:
            problems.append(
                "new_provider is required: the TCK has nothing to test without it"
            )

        # Normalise whatever iterable the caller passed into a frozenset, so a
        # set literal, a list or a generator all behave the same.
        object.__setattr__(self, "capabilities", frozenset(self.capabilities))

        unknown = [c for c in self.capabilities if not isinstance(c, Capability)]
        if unknown:
            problems.append(
                f"unknown capabilities {unknown!r}: capabilities are the members of "
                f"the Capability enum"
            )

        object.__setattr__(self, "known_deviations", tuple(self.known_deviations))

        problems.extend(reserved_problems(self.capabilities))

        if (
            Capability.UNAVAILABLE_INIT in self.capabilities
            and self.new_unavailable_provider is None
        ):
            problems.append(
                "capabilities declares Capability.UNAVAILABLE_INIT but "
                "new_unavailable_provider is None: the @unavailable scenarios need a "
                "provider pointed at a backend that does not exist. Supply one, or "
                "remove the capability so those scenarios are skipped with a reason"
            )

        if problems:
            joined = "\n  - ".join(problems)
            msg = f"invalid TckConfig:\n  - {joined}"
            raise ValueError(msg)

    @property
    def domain(self) -> str:
        """The OpenFeature domain this suite registers its providers under.

        Suite-scoped rather than scenario-scoped on purpose. Registering a new
        provider in the same domain replaces the previous one; a fresh domain
        per scenario would leave every provider of the suite registered, which
        for a provider holding a network connection means leaking one connection
        per scenario.
        """
        return f"provider-tck/{self.name}"

    def declares(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def sorted_capabilities(self) -> list[str]:
        return sorted(c.tag for c in self.capabilities)


def reserved_problems(declared: Iterable[Capability]) -> list[str]:
    """Refuse a reserved capability named in a configuration.

    A reserved capability gates no scenario, so declaring it cannot be verified
    either way: the claim is about something nothing examined, and it would
    reach the report's declaration, which the schema forbids.

    Refused rather than dropped quietly. The adopter wrote it down and meant
    something by it, so a configuration silently different from the one they
    wrote is worse than one that will not build -- and construction is where
    their own code is still on the stack to say which line to fix. The
    alternative, a warning, is a line of CI output nobody reads while an
    untested capability goes on being asserted in a published report, which is
    how this got into one in the first place.
    """
    reserved = sorted(
        capability.tag
        for capability in declared
        if isinstance(capability, Capability) and capability.reserved
    )
    if not reserved:
        return []
    declarable = " ".join(sorted(c.tag for c in DECLARABLE_CAPABILITIES))
    return [
        f"reserved capabilities {' '.join(sorted(set(reserved)))} cannot be declared: "
        f"no scenario carries them, so the claim cannot be verified, cannot produce a "
        f"skip, and would tell a reader of the report only that something was claimed "
        f"and nothing examined. The declarable capabilities, which is what "
        f"DECLARABLE_CAPABILITIES holds, are {declarable}"
    ]


def capabilities_of(values: Iterable[Capability]) -> frozenset[Capability]:
    """Convenience for building a capability set from any iterable."""
    return frozenset(values)
