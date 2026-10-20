"""The seam between the scenarios and whatever manipulates the backend."""

from __future__ import annotations

import typing

__all__ = [
    "DEFAULT_BACKEND_TYPE",
    "BackendControl",
    "BackendType",
    "ConnectionControl",
    "UnsupportedControlError",
    "backend_type_of",
    "unsupported_control",
]

BackendType = typing.Literal["http", "in-process", "custom"]
"""How the backend under test was driven, closed to the values the schema allows.

``"http"`` is the normative HTTP control API in ``control-api.yaml``.
``"in-process"`` is the narrow allowance for a provider with no backend.
``"custom"`` is a control this package does not ship, driving the backend some
way the suite cannot vouch for -- the honest answer where neither of the other
two is true, and better in a report than a claim to a normative path that was
not taken.

Named so that a custom control can annotate its own property with it and have
the type checker refuse a fourth value before it becomes a conformance report
that fails validation with nothing to point at locally.
"""

DEFAULT_BACKEND_TYPE: BackendType = "custom"
"""What an unstated backend type resolves to: the weakest honest claim.

Silence cannot mean ``"http"`` or ``"in-process"`` -- those are claims about the
path a run took, and only the control knows which it drove.
"""


class UnsupportedControlError(RuntimeError):
    """Raised when a backend cannot perform a control operation.

    Always a test-configuration bug rather than a provider defect: the scenarios
    needing connection control are gated behind :attr:`Capability.STALE` and
    :attr:`Capability.UNAVAILABLE_INIT`, so reaching an unsupported operation
    means a capability was declared that the backend cannot back up. Raised
    rather than skipped, because a silent no-op would report the scenario as
    passed.
    """


@typing.runtime_checkable
class BackendControl(typing.Protocol):
    """How the TCK puts the backend under test into the states a scenario needs.

    Step definitions never talk to a backend directly. They talk to this
    protocol, which is why the same Gherkin runs unchanged against a
    containerised backend driven over HTTP and against a provider manipulated
    in-process.

    **Which implementation is right for your provider.** If your provider talks
    to a backend -- a server, a service, anything out of process -- drive it over
    the HTTP control API in ``control-api.yaml``. That API is the normative
    contract for those providers, and it is what makes a conformance claim
    portable: another language's TCK drives the same endpoints against the same
    stack and must get the same answers.

    Do not instead write an in-process control that reaches into an external
    backend through a side channel -- a test-only admin client, a shared database
    handle, a hook inside the provider. It will pass and prove nothing, because
    the path it exercised is not the path the contract describes. In-process
    control is for providers with *no* backend to contract with; see
    :class:`InProcessControl`.

    **Saying how the backend was driven.** A control may expose a
    ``backend_type`` property typed :data:`BackendType`, naming the path it
    drove. It is deliberately *not* a member of this protocol: Python has no
    optional protocol member -- declaring it, even with a default
    implementation, makes it required of every implementation both to a type
    checker and to :func:`isinstance` -- so it is left out and read through
    :func:`backend_type_of`, which resolves an absent one to
    :data:`DEFAULT_BACKEND_TYPE`. Both controls this package ships state theirs;
    an adopter writing their own and saying nothing gets ``"custom"``, which is
    the honest report for a path the suite cannot vouch for.
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


def backend_type_of(control: BackendControl) -> BackendType:
    """Resolve how a control drove the backend, for the conformance report.

    An absent ``backend_type`` resolves to :data:`DEFAULT_BACKEND_TYPE` rather
    than being inferred from the concrete type: nothing outside a control can
    tell the normative HTTP path from in-process manipulation of a provider that
    *does* have a backend, so a guess here would put an unfalsifiable claim in a
    report. A control that does state one is believed -- it is the only thing
    that knows.
    """
    stated = getattr(control, "backend_type", DEFAULT_BACKEND_TYPE)
    return typing.cast("BackendType", stated)


def unsupported_control(
    control: BackendControl, operation: str
) -> UnsupportedControlError:
    """Build the error raised when a backend has no connection to control."""
    return UnsupportedControlError(
        f"{control.description} does not support {operation!r}. This is a "
        f"test-configuration bug rather than a provider defect: a scenario needing "
        f"connection control ran, so the suite declared Capability.STALE or "
        f"Capability.UNAVAILABLE_INIT for a backend that cannot simulate an outage. "
        f"Remove those capabilities from TckConfig.capabilities, or supply a "
        f"BackendControl that also implements ConnectionControl."
    )
