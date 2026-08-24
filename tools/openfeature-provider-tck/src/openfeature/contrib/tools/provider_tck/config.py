"""The contract a provider author implements to run the suite."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from openfeature.provider import FeatureProvider

from .capability import ALL_CAPABILITIES, Capability
from .control import BackendControl

__all__ = ["ProviderFactory", "TckConfig"]

ProviderFactory = Callable[[], FeatureProvider]
"""Creates the provider under test.

A factory rather than a single instance because each scenario gets its own
provider, and because a provider often cannot be configured before the suite
starts -- a container stack's host ports do not exist until it is up.
"""

DEFAULT_EVENT_TIMEOUT = 12.0
DEFAULT_READY_TIMEOUT = 30.0


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

    capabilities: frozenset[Capability] = field(default=ALL_CAPABILITIES)
    """Which optional parts of the provider contract this provider supports.

    Scenarios tagged with an undeclared capability are reported as skipped with
    the reason, never as passed. Defaults to everything; narrow it rather than
    widening it.
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
    """Seconds to wait for a provider to reach ``READY`` during initialisation."""

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


def capabilities_of(values: Iterable[Capability]) -> frozenset[Capability]:
    """Convenience for building a capability set from any iterable."""
    return frozenset(values)
