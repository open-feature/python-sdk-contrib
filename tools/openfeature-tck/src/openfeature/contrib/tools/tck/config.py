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

    **An entry says: this provider fails to do something it is required to do.**
    Distinct from an undeclared capability, which is a *choice* the provider is
    entitled to make. Appendix F's declaring rules say which of the two fits a
    given gap, and when neither does -- a scenario failing because the backend
    serves no fixture for it is not a provider defect and does not belong here.

    It changes nothing about how the suite runs: the scenario still fails and the
    results payload still reports it as failed. What this adds is the
    acknowledgement, in the envelope, so a consumer can tell a known gap from a
    surprise.

    Build one with :meth:`tracked` or :meth:`untracked` rather than by calling
    the constructor, so that which of the two a deviation is stays a decision
    someone made rather than a field someone forgot.
    """

    summary: str
    """What is wrong, for a person reading a comparison page.

    Required. A deviation with no summary records that something is wrong without
    saying what, which is worth less than the bare skip or failure it
    accompanies.
    """

    issue: str | None = None
    """Where the gap is tracked, or ``None`` when it is tracked nowhere yet.

    Prefer :meth:`tracked` as soon as there is an issue to point at.
    """

    capability: Capability | None = None
    """The capability the deviation concerns, when it maps to one.

    Left out when the gap is against a mandatory, ungated scenario, which belongs
    to no capability. A reserved capability is refused, and so is one this SDK
    cannot express -- see :func:`deviation_problems`.
    """

    @classmethod
    def tracked(
        cls,
        summary: str,
        issue: str,
        capability: Capability | None = None,
    ) -> KnownDeviation:
        """Record a deviation that is tracked somewhere.

        :param summary: what the gap is.
        :param issue: a URI where it is tracked.
        :param capability: the capability the gap concerns, or ``None`` when the
            gap is against a mandatory scenario and so belongs to no capability.
        """
        return cls(summary=summary, issue=issue, capability=capability)

    @classmethod
    def untracked(
        cls,
        summary: str,
        capability: Capability | None = None,
    ) -> KnownDeviation:
        """Record a deviation that is not tracked anywhere yet.

        Worth declaring even so: naming the defect is what separates it from a
        capability the provider chose to withhold. Prefer :meth:`tracked` as soon
        as there is an issue to point at.

        :param summary: what the gap is.
        :param capability: the capability the gap concerns, or ``None`` when the
            gap is against a mandatory scenario and so belongs to no capability.
        """
        return cls(summary=summary, capability=capability)

    @property
    def is_tracked(self) -> bool:
        """Whether this deviation points at somewhere the gap is tracked."""
        return bool(self.issue)

    def as_json(self) -> dict[str, typing.Any]:
        document: dict[str, typing.Any] = {"summary": self.summary}
        # Omitted rather than null: the schema's `issue` is a uri-formatted
        # string when present, so an untracked deviation leaves the key out.
        if self.issue is not None:
            document["issue"] = self.issue
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

    Scenarios tagged with an undeclared capability are reported as skipped with
    the reason, never as passed. Defaults to
    :data:`~.capability.DECLARABLE_CAPABILITIES`; narrowing it surfaces gaps
    where widening towards it hides them.

    Typed as a ``Collection`` so that a set literal, a list or a generator all
    behave identically -- it is normalised to a frozenset on construction.

    A reserved capability named here is rejected at construction, and so is one
    this language's SDK cannot put the question for at all. The two refusals are
    deliberately not the same message: see :func:`reserved_problems` and
    :func:`inexpressible_problems`.
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
        problems.extend(inexpressible_problems(self.capabilities))
        problems.extend(deviation_problems(self.known_deviations))

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

        Suite-scoped rather than scenario-scoped: registering a new provider in
        the same domain replaces the previous one, where a fresh domain per
        scenario would leave every provider of the suite registered and, for a
        provider holding a network connection, leak one connection per scenario.
        """
        return f"tck/{self.name}"

    def declares(self, capability: Capability) -> bool:
        return capability in self.capabilities

    @property
    def sorted_capabilities(self) -> list[str]:
        return sorted(c.tag for c in self.capabilities)


def reserved_problems(declared: Iterable[Capability]) -> list[str]:
    """Refuse a reserved capability named in a configuration.

    A reserved capability gates no scenario, so declaring it cannot be verified
    either way, and it would reach the report's declaration, which the schema
    forbids.

    Refused rather than dropped quietly or warned about: the adopter wrote it
    down and meant something by it, and construction is where their own code is
    still on the stack to say which line to fix.
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


def inexpressible_problems(declared: Iterable[Capability]) -> list[str]:
    """Refuse a capability this language's SDK cannot put the question for.

    Refused here rather than left to adopters, because otherwise every adopter in
    the language has to know a fact about their language and remember to act on
    it, and a single wrong one puts a claim in a report that no scenario could
    have verified.

    **The message names the property of the SDK, not the rule.** An adopter who
    reaches this has done nothing wrong, so the error has to tell them something
    they could not have known.

    Separate from :func:`reserved_problems` even though both end in a refusal. A
    reserved capability is global and temporary; an inexpressible one is this
    language's and permanent. Collapsing them would make the two
    indistinguishable at the only moment anybody is looking.
    """
    refused = [
        capability
        for capability in declared
        if isinstance(capability, Capability) and capability.inexpressible
    ]
    if not refused:
        return []
    return [
        f"{capability.tag} cannot be declared in this language: {reason}. No "
        f"provider in this SDK can be asked the question its scenarios put, so a "
        f"declaration could not be verified either way, and its absence from a "
        f"report says nothing about your provider. Its scenarios are skipped with "
        f"that reason. This is not a reservation -- the scenarios exist and other "
        f"languages run them -- and there is nothing for you to fix; it changes "
        f"when the SDK does"
        for capability in sorted(refused, key=lambda c: c.tag)
        if (reason := capability.inexpressible_reason) is not None
    ]


def deviation_problems(deviations: Sequence[KnownDeviation]) -> list[str]:
    """Refuse a deviation that says nothing a consumer can use.

    The rules are deliberately narrow. A deviation is prose written for a human
    comparing providers, and no suite can check prose; what it can check is that
    the prose is there and that the capability it names is one a scenario could
    have been gated on.
    """
    problems: list[str] = []

    for index, deviation in enumerate(deviations):
        if not deviation.summary or not deviation.summary.strip():
            problems.append(
                f"known_deviations[{index}] has no summary: a deviation exists to "
                f"say what the gap is, and one that does not say it leaves a "
                f"consumer no better off than the bare skip or failure it "
                f"accompanies. It is the one field the report schema requires"
            )

        capability = deviation.capability
        if capability is None:
            # Legitimate: the gap is against a mandatory, ungated scenario,
            # which belongs to no capability.
            continue

        if not isinstance(capability, Capability):
            problems.append(
                f"known_deviations[{index}] names unknown capability "
                f"{capability!r}: capabilities are the members of the Capability "
                f"enum"
            )
            continue

        if capability.reserved:
            problems.append(
                f"known_deviations[{index}] names the reserved capability "
                f"{capability.tag}: no scenario carries that tag, so nothing was "
                f"failed or skipped for this deviation to explain and no result "
                f"could show the gap. Remove it, or name the capability whose "
                f"scenarios the gap actually affects"
            )
        elif capability.inexpressible:
            problems.append(
                f"known_deviations[{index}] names {capability.tag}, which cannot "
                f"be expressed in this language: {capability.inexpressible_reason}. "
                f"A deviation says this provider fails something it is required to "
                f"do, and no provider in this SDK can attempt these scenarios at "
                f"all -- so the entry would attribute to your provider a gap that "
                f"belongs to the language. The skip already carries that reason"
            )

    return problems


def capabilities_of(values: Iterable[Capability]) -> frozenset[Capability]:
    """Convenience for building a capability set from any iterable."""
    return frozenset(values)
