"""The seam between the scenarios and whatever manipulates the backend."""

from __future__ import annotations

import typing

__all__ = [
    "BackendControl",
    "ConnectionControl",
    "ControlApi",
    "UnsupportedControlError",
    "unsupported_control",
]

ControlApi = typing.Literal["http", "in-process"]
"""Which of the two control paths a run used, closed to the two the schema allows.

Named so that a custom control can annotate its own property with it and have
the type checker refuse a third value -- ``"HTTP"``, ``"grpc"``, a typo -- before
it becomes a conformance report that fails validation with nothing to point at
locally.
"""


class UnsupportedControlError(RuntimeError):
    """Raised when a backend cannot perform a control operation.

    It is always a test-configuration bug rather than a provider defect. The
    scenarios needing connection control are gated behind
    :attr:`Capability.STALE` and :attr:`Capability.UNAVAILABLE_INIT`, so
    reaching an unsupported operation means a capability was declared that the
    backend cannot back up. The TCK fails loudly on it rather than skipping,
    because a silent no-op would report the scenario as passed.
    """


@typing.runtime_checkable
class BackendControl(typing.Protocol):
    """How the TCK puts the backend under test into the states a scenario needs.

    Step definitions never talk to a backend directly. They talk to this
    protocol, which is why the same Gherkin runs unchanged against a
    containerised backend driven over HTTP and against a provider manipulated
    in-process. Nothing below this line knows about ports, containers or
    transports.

    **Which implementation is right for your provider.** If your provider talks
    to a backend -- a server, a service, anything out of process -- drive it
    over the HTTP control API described in ``control-api.yaml``. That API is the
    normative contract for those providers, and it is what makes a conformance
    claim portable: another language's TCK drives the same endpoints against the
    same stack and must get the same answers.

    Do not write an in-process control that reaches into an external backend
    through a side channel -- a test-only admin client, a shared database
    handle, a hook inside the provider. It will pass, and it will prove nothing,
    because the path it exercised is not the path the contract describes.

    In-process control exists for providers with *no* backend to contract with:
    in-memory, environment-variable and file-based providers, where "the
    backend" is a data structure in the same process. See
    :class:`InProcessControl`.
    """

    def prepare_scenario(self) -> None:
        """Bring the backend to the state every scenario starts from.

        Reachable, with flag state at the baseline of the canonical flag set.
        Called once before each scenario. This is the TCK's only isolation
        mechanism -- scenarios share one backend for the whole suite, and
        containers are never restarted between them.
        """

    def change_flag(self) -> None:
        """Mutate flag configuration so a conforming provider observes a change.

        Afterwards the provider must resolve a different value for
        ``changing-flag``. Which value it changes to is deliberately
        unspecified; the suite asserts only that the resolved value differs.
        """

    @property
    def description(self) -> str:
        """A short description of what is being controlled, for messages a human reads."""

    @property
    def control_api(self) -> ControlApi:
        """Which path this control drove the backend through.

        ``"http"`` is the normative HTTP control API in ``control-api.yaml``.
        ``"in-process"`` is the narrow allowance made for a provider with no
        backend, where "the backend" is a data structure in this process -- see
        :class:`InProcessControl`.

        **Required, and stated rather than inferred.** It is the one fact that
        decides what everything else in a report is worth: the same scenarios
        passing over the control API and passing through in-process manipulation
        of a provider that *does* have a backend are not the same claim, and
        this is the only field that separates them. Nothing outside a control can
        tell the two apart -- a suite that guessed from the control's concrete
        type would be right about the two controls in this package and silently
        wrong about a custom one, which is exactly the case where the answer
        matters.

        Nor would an absent value be neutral. Every run is one or the other, so
        there is no third case an omitted value legitimately covers: it would
        not be "no claim made" but an unfalsifiable one. A custom control states
        it here and nothing downstream has to guess.
        """


@typing.runtime_checkable
class ConnectionControl(typing.Protocol):
    """Implemented by a backend that can be cut off from the provider and restored.

    Separate from :class:`BackendControl` so a backend-less provider cannot
    accidentally supply a no-op implementation: not implementing it at all is
    the honest answer, and the TCK turns the resulting gap into an explicit,
    reported skip.
    """

    def disconnect(self) -> None:
        """Make the backend unreachable for the rest of the scenario, without stopping a container."""

    def reconnect(self) -> None:
        """Make the backend reachable again, preserving flag state.

        Preserving flag state is a requirement, not an implementation detail. An
        outage must be observable as a change in availability and never as a
        change in flag values, or the stale scenario cannot distinguish the two.
        """


def unsupported_control(
    control: BackendControl, operation: str
) -> UnsupportedControlError:
    """Build the error raised when a backend has no connection to control.

    The message names the fix, because the mistake it reports is always the same
    one.
    """
    return UnsupportedControlError(
        f"{control.description} does not support {operation!r}. This is a "
        f"test-configuration bug rather than a provider defect: a scenario needing "
        f"connection control ran, so the suite declared Capability.STALE or "
        f"Capability.UNAVAILABLE_INIT for a backend that cannot simulate an outage. "
        f"Remove those capabilities from TckConfig.capabilities, or supply a "
        f"BackendControl that also implements ConnectionControl."
    )
