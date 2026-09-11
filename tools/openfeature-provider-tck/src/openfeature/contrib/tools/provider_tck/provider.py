"""An in-memory provider that can be reconfigured at runtime, and the canonical flag set."""

from __future__ import annotations

import typing

from openfeature.event import ProviderEventDetails
from openfeature.provider.in_memory_provider import (
    FlagStorage,
    InMemoryFlag,
    InMemoryProvider,
)

__all__ = [
    "CHANGING_FLAG_KEY",
    "ControllableInMemoryProvider",
    "canonical_flag_set",
    "changing_flag",
]

CHANGING_FLAG_KEY = "changing-flag"
"""The flag :meth:`BackendControl.change_flag` mutates."""

_CHANGING_BASELINE = "foo"
_CHANGING_CHANGED = "bar"


class ControllableInMemoryProvider(InMemoryProvider):
    """An in-memory provider whose flag set can be replaced at runtime.

    **Why this exists.** `Appendix A`_ of the specification requires an SDK's
    in-memory provider to "support a means of updating the ``flag set``,
    resulting in the emission of ``PROVIDER_CONFIGURATION_CHANGED`` events". The
    Python SDK's :class:`~openfeature.provider.in_memory_provider.InMemoryProvider`
    has no such method: it copies the flag mapping in its constructor and never
    exposes a way to change it.

    Only half the machinery is missing, which is what makes this a small class
    rather than a reimplementation. :class:`~openfeature.provider.AbstractProvider`
    already supplies ``emit_provider_configuration_changed``, and the registry
    already attaches the emitter, so all that is needed is a method that swaps
    the mapping and emits. Everything about *resolution* -- variants, reasons,
    ``FLAG_NOT_FOUND`` -- is still the SDK's.

    That makes this an honest reference for what the SDK's provider should grow,
    rather than a competing implementation that could drift from it.

    .. _Appendix A: https://github.com/open-feature/spec/blob/main/specification/appendix-a-included-utilities.md
    """

    def update_flags(self, flags: FlagStorage) -> None:
        """Replace the whole flag set and emit a configuration-change event.

        The event names the union of the previous and new keys, which is what
        Appendix A asks for: a consumer caching evaluations needs to know
        everything that might have changed, and a key that disappeared has
        changed as much as one that was added.
        """
        changed = sorted(set(self._flags) | set(flags))
        self._flags = dict(flags)
        self.emit_provider_configuration_changed(
            ProviderEventDetails(
                flags_changed=changed, message="flag configuration changed"
            )
        )

    def update_flag(self, key: str, flag: InMemoryFlag[typing.Any]) -> None:
        """Replace a single flag and emit a configuration-change event naming it."""
        updated = dict(self._flags)
        updated[key] = flag
        self._flags = updated
        self.emit_provider_configuration_changed(
            ProviderEventDetails(
                flags_changed=[key], message="flag configuration changed"
            )
        )

    def flag(self, key: str) -> InMemoryFlag[typing.Any] | None:
        """Return the flag currently registered under ``key``."""
        return self._flags.get(key)


def changing_flag(default_variant: str) -> InMemoryFlag[str]:
    return InMemoryFlag(
        default_variant=default_variant,
        variants={
            _CHANGING_BASELINE: _CHANGING_BASELINE,
            _CHANGING_CHANGED: _CHANGING_CHANGED,
        },
    )


def canonical_flag_set() -> FlagStorage:
    """Return the canonical flag set as SDK in-memory flags.

    Mirrors ``flag_data/canonical-flags.json`` entry for entry -- and the
    self-tests check that it does, value for value and Python type for Python
    type. Four properties of that file are load-bearing and hold here too:

    * ``missing-flag`` is absent, which is what the ``FLAG_NOT_FOUND`` scenario
      tests. Adding it turns that scenario green for the wrong reason.
    * no flag carries a ``context_evaluator``, so every evaluation reports reason
      ``STATIC`` -- the TCK tests a provider's mapping of a response, not a
      backend's evaluation logic.
    * ``boolean-zero-flag``, ``integer-zero-flag`` and ``string-zero-flag``
      resolve to ``False``, ``0`` and ``""``. They are values, not absences, and
      the falsy scenarios exist to catch a provider that cannot tell the
      difference. Their ``zero``/``non-zero`` variant names are load-bearing
      too: the scenarios assert the variant, not only the value.
    * ``integral-float-flag`` is the ``float`` ``10.0`` and ``huge-integer-flag``
      is the ``int`` ``9007199254740991``. Writing the first as ``10`` makes the
      lossless-coercion scenario pass without coercing; nothing here goes
      through a float, so the second cannot be rounded.
    """
    return {
        "boolean-flag": InMemoryFlag(
            default_variant="on", variants={"on": True, "off": False}
        ),
        "string-flag": InMemoryFlag(
            default_variant="greeting", variants={"greeting": "hi", "parting": "bye"}
        ),
        "integer-flag": InMemoryFlag(
            default_variant="ten", variants={"one": 1, "ten": 10}
        ),
        "float-flag": InMemoryFlag(
            default_variant="half", variants={"tenth": 0.1, "half": 0.5}
        ),
        # 2^31 - 1: the largest value every language's integer accessor can ask for.
        "large-integer-flag": InMemoryFlag(
            default_variant="max-int32", variants={"one": 1, "max-int32": 2147483647}
        ),
        # 2^53 - 1: asked for only under @large-integers. A Python int is exact.
        "huge-integer-flag": InMemoryFlag(
            default_variant="max-safe",
            variants={"one": 1, "max-safe": 9007199254740991},
        ),
        # A float with no fractional part, for the lossless half of
        # @numeric-coercion. The trailing ``.0`` is the whole point.
        "integral-float-flag": InMemoryFlag(
            default_variant="ten", variants={"tenth": 0.1, "ten": 10.0}
        ),
        "boolean-zero-flag": InMemoryFlag(
            default_variant="zero", variants={"zero": False, "non-zero": True}
        ),
        "integer-zero-flag": InMemoryFlag(
            default_variant="zero", variants={"zero": 0, "non-zero": 1}
        ),
        "string-zero-flag": InMemoryFlag(
            default_variant="zero", variants={"zero": "", "non-zero": "str"}
        ),
        "object-flag": InMemoryFlag(
            default_variant="template",
            variants={
                "empty": {},
                "template": {
                    "showImages": True,
                    "title": "Check out these pics!",
                    "imagesPerPage": 100,
                },
            },
        ),
        # A string flag, evaluated as a boolean by the TYPE_MISMATCH scenario.
        "wrong-flag": InMemoryFlag(
            default_variant="one", variants={"one": "uno", "two": "dos"}
        ),
        CHANGING_FLAG_KEY: changing_flag(_CHANGING_BASELINE),
    }
