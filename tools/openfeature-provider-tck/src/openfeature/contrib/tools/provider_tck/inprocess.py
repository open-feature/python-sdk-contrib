"""In-process backend control, for providers with no backend at all."""

from __future__ import annotations

from openfeature.provider import FeatureProvider

from .provider import (
    CHANGING_FLAG_KEY,
    ControllableInMemoryProvider,
    canonical_flag_set,
    changing_flag,
)

__all__ = ["InProcessControl"]

_BASELINE = "foo"
_CHANGED = "bar"


class InProcessControl:
    """Manipulates an in-process provider directly, with no backend and no HTTP.

    This exists so providers with nothing to connect to -- in-memory,
    environment-variable and file-based providers -- can run the TCK. For those,
    "the backend" is a data structure in the same process: seeding flags is
    building a mapping, and changing one is an update on the live provider, so
    the event the suite awaits is the provider's own
    ``PROVIDER_CONFIGURATION_CHANGED`` rather than one the TCK synthesised.

    **This is not a shortcut for providers that do have a backend.** Reaching
    into an external backend from inside the test process -- a test-only admin
    client, a shared database handle, a hook in the provider -- produces a suite
    that passes while proving nothing, because the path it exercised is not the
    path the contract describes. Those providers drive the HTTP control API
    instead.

    **Connection control.** :class:`InProcessControl` deliberately does not
    implement :class:`~.control.ConnectionControl`. An in-memory provider has no
    connection to lose, and pretending otherwise with a no-op would report the
    ``@stale`` scenarios as passed. A suite using it leaves
    :attr:`Capability.STALE` and :attr:`Capability.UNAVAILABLE_INIT` undeclared,
    and those scenarios are skipped with the reason reported.

    **Ownership of the provider.** This type both seeds the flags and creates
    the provider serving them, because in-process they are the same object:
    :meth:`change_flag` has to reach the live instance to emit an event from it.
    A suite therefore wires both through one control::

        control = InProcessControl()
        TckConfig(
            name="in-memory",
            control=control,
            new_provider=control.new_provider,
            capabilities={Capability.EVENTS, Capability.CONFIGURATION_CHANGE},
        )
    """

    def __init__(self) -> None:
        self._current: ControllableInMemoryProvider | None = None
        self._changing_variant = _BASELINE

    @property
    def description(self) -> str:
        return "in-process control of an in-memory provider"

    def new_provider(self) -> FeatureProvider:
        """Create the provider for the scenario about to run, at the baseline.

        Each call returns a fresh instance over a fresh copy of the canonical
        flag set, which is what makes :meth:`prepare_scenario` nothing more than
        dropping the previous reference.
        """
        self._changing_variant = _BASELINE
        self._current = ControllableInMemoryProvider(canonical_flag_set())
        return self._current

    def prepare_scenario(self) -> None:
        """Drop the previous scenario's provider.

        That is the whole reset: the flag set is rebuilt per provider, so the
        :meth:`new_provider` call that follows starts from an untouched
        baseline. Clearing the reference rather than leaving it dangling means a
        scenario that changes flags without creating a provider fails with a
        clear message instead of mutating one that has already been shut down.
        """
        self._current = None

    def change_flag(self) -> None:
        """Flip ``changing-flag`` between its two variants on the live provider.

        The event the suite awaits is therefore the provider's own
        ``PROVIDER_CONFIGURATION_CHANGED``, carrying ``changing-flag`` in
        ``flags_changed``, and not a signal the TCK synthesised.

        Alternating rather than assigning a fixed variant keeps repeated calls
        within one scenario meaningful; the suite asserts that the resolved
        value differs, not what it became.
        """
        if self._current is None:
            msg = (
                "No in-memory provider exists for this scenario. In-process control "
                "manipulates the provider itself, so the scenario must create one -- "
                'with "Given a stable provider" -- before any step that changes flag state.'
            )
            raise RuntimeError(msg)

        self._changing_variant = (
            _BASELINE if self._changing_variant == _CHANGED else _CHANGED
        )
        self._current.update_flag(
            CHANGING_FLAG_KEY, changing_flag(self._changing_variant)
        )
