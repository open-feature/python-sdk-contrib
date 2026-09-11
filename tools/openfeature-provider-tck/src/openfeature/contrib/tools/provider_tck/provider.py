"""An in-memory provider that can be reconfigured at runtime, and the canonical flag set."""

from __future__ import annotations

import importlib.resources
import json
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
    "canonical_flags_json",
    "changing_flag",
]

CHANGING_FLAG_KEY = "changing-flag"
"""The flag :meth:`BackendControl.change_flag` mutates."""

_CHANGING_BASELINE = "foo"
_CHANGING_CHANGED = "bar"

_PACKAGE = "openfeature.contrib.tools.provider_tck"

_FLAG_DATA_DIRECTORY = "flag_data"
_CANONICAL_FLAGS_FILE = "canonical-flags.json"

_COMMENT_KEY = "$comment"
"""The key the specification's assets carry prose under.

Ignored at the document level, at a flag's level and among a flag's *variant
names* -- a "variant" called ``$comment`` is prose about the flag rather than a
variant of it -- and deliberately **not** inside a variant's value. A value is
opaque data the suite passes through: ``object-flag`` could perfectly well grow
a member of that name, and a loader that reached into a value to strip it would
serve an object no scenario expects. JavaScript's suite draws the line in the
same place, on purpose.
"""


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
    """Build ``changing-flag`` at one of its two variants.

    The one flag built by hand rather than decoded, because
    :meth:`InProcessControl.change_flag` has to rebuild it at the *other*
    variant and so has to name both. That the names here are the ones the
    canonical file defines is asserted by the self-tests rather than assumed.
    """
    return InMemoryFlag(
        default_variant=default_variant,
        variants={
            _CHANGING_BASELINE: _CHANGING_BASELINE,
            _CHANGING_CHANGED: _CHANGING_CHANGED,
        },
    )


def canonical_flags_json() -> str:
    """Return the canonical flag set as raw JSON, in the flagd flag-definition format.

    This is the flag set every scenario assumes, and a backend under test must
    serve an equivalent one. The format is not what matters -- the keys, types,
    variant names and resolved values are. Seed them however your backend seeds
    flags.

    Exposed so an adopting provider can seed a backend from the canonical
    definition rather than transcribing it, transcription being the usual way
    the two drift apart. :func:`canonical_flag_set` takes its own advice.
    """
    ref = (
        importlib.resources.files(_PACKAGE)
        / _FLAG_DATA_DIRECTORY
        / _CANONICAL_FLAGS_FILE
    )
    return ref.read_text(encoding="utf-8")


def canonical_flag_set() -> FlagStorage:
    """Return the canonical flag set as SDK in-memory flags.

    Decoded from ``flag_data/canonical-flags.json`` -- the JSON
    :func:`canonical_flags_json` returns -- rather than transcribed, so that the
    in-memory suites cannot drift from the file every other language seeds a
    backend from. That file is published precisely so an adopter can "seed a
    backend directly from the canonical definition rather than transcribing it,
    transcription being the usual way the two drift apart"; this suite is an
    adopter of it like any other.

    The drift it prevents is silent rather than loud. A fixture that has moved
    away from the file makes the in-memory self-tests pass against a baseline
    that is no longer the canonical one, so the suite verifies itself against
    the wrong flags while reporting green -- and the report it publishes claims
    the canonical set.

    Four properties of the file are load-bearing, and all four survive the
    decoding:

    * ``missing-flag`` is absent, which is what the ``FLAG_NOT_FOUND`` scenario
      tests. Adding it turns that scenario green for the wrong reason.
    * no flag carries a ``context_evaluator``, so every evaluation reports reason
      ``STATIC``. ``targeting-key-flag`` is the one flag in the file with a
      ``targeting`` member, and this decoder reads only ``state``, ``variants``
      and ``defaultVariant`` -- so that flag is served at its ``miss`` default
      whatever the context, like every other. That is deliberate rather than
      pending: decoding a rule language would make this package a second
      implementation of somebody else's evaluator, and the untargeted scenarios
      are the ones it exists to serve. The consequence is that an in-memory
      adoption must leave :attr:`~.capability.Capability.TARGETING` undeclared,
      and its three scenarios are skipped with that reason.
    * ``boolean-zero-flag``, ``integer-zero-flag`` and ``string-zero-flag``
      resolve to ``False``, ``0`` and ``""``. They are values, not absences, and
      the falsy scenarios exist to catch a provider that cannot tell the
      difference. Their ``zero``/``non-zero`` variant names are load-bearing
      too, for an adoption declaring
      :attr:`~.capability.Capability.VARIANTS`: the gated variant scenario
      asserts the variant, where the falsy scenarios assert only the value.
    * a number keeps the type it was written with. ``json.loads`` gives ``int``
      for ``10``, ``float`` for ``10.0`` and an arbitrary-precision ``int`` for
      2^53 - 1, and nothing here normalises either way, so
      ``integral-float-flag`` stays the ``float`` ``10.0`` and
      ``huge-integer-flag`` stays exact. Normalising integral floats to ``int``
      is the decoder bug that bit Java, and it makes the lossless-coercion
      scenario pass without coercing anything.

    A variant's value is passed through untouched, which is both why the types
    survive and why a ``$comment`` member *inside* an object value survives with
    them -- see :data:`_COMMENT_KEY`.

    Raises:
        ValueError: if the packaged file is not the shape this expects.
            Unreachable for a pinned spec revision, because the file is copied
            in from the submodule at build time: a failure here means the pinned
            assets and this decoder disagree about the file's shape, which
            moving the pin should have surfaced.
    """
    return _decode_canonical_flags(canonical_flags_json())


def _decode_canonical_flags(raw: str) -> FlagStorage:
    """Turn the canonical flag file into in-memory flags."""
    document = json.loads(raw)
    if not isinstance(document, dict):
        msg = f"{_CANONICAL_FLAGS_FILE} is not a JSON object"
        raise ValueError(msg)

    # Reading the one member this needs is what ignores $comment at the document
    # level, along with every other part of the flagd format the suite has no
    # use for.
    definitions = document.get("flags")
    if not isinstance(definitions, dict) or not definitions:
        msg = f"{_CANONICAL_FLAGS_FILE} defines no flags"
        raise ValueError(msg)

    return {key: _decode_flag(key, value) for key, value in definitions.items()}


def _decode_flag(key: str, definition: typing.Any) -> InMemoryFlag[typing.Any]:
    """Turn one flag definition into an in-memory flag, or say why it cannot be."""
    if not isinstance(definition, dict):
        msg = f"flag {key!r}: expected an object, got {type(definition).__name__}"
        raise ValueError(msg)

    variants = definition.get("variants")
    if not isinstance(variants, dict):
        msg = f"flag {key!r}: variants is not an object"
        raise ValueError(msg)
    # Only the variant *names* are filtered. The values are not looked into.
    variants = {name: value for name, value in variants.items() if name != _COMMENT_KEY}

    default_variant = definition.get("defaultVariant")
    if not isinstance(default_variant, str) or default_variant not in variants:
        msg = (
            f"flag {key!r}: default variant {default_variant!r} is not one of its "
            f"variants ({', '.join(sorted(map(repr, variants)))})"
        )
        raise ValueError(msg)

    raw_state = definition.get("state")
    try:
        state = InMemoryFlag.State(raw_state)
    except ValueError:
        allowed = ", ".join(member.value for member in InMemoryFlag.State)
        msg = f"flag {key!r}: state {raw_state!r} is none of {allowed}"
        raise ValueError(msg) from None

    return InMemoryFlag(default_variant=default_variant, variants=variants, state=state)
