"""Things the Gherkin cannot assert about itself.

Each of these is a way the in-process control path could look correct while
quietly making the conformance suites meaningless.
"""

from __future__ import annotations

import json
import typing
from collections.abc import Callable

import pytest

from openfeature.contrib.tools.provider_tck import (
    CHANGING_FLAG_KEY,
    ConnectionControl,
    ControllableInMemoryProvider,
    InProcessControl,
    canonical_flag_set,
    canonical_flags_json,
)
from openfeature.contrib.tools.provider_tck.provider import (
    _decode_canonical_flags,
    changing_flag,
)
from openfeature.contrib.tools.provider_tck.values import describe, values_equal
from openfeature.event import ProviderEvent
from openfeature.flag_evaluation import FlagType, Reason

_NOT_SEEDED = "this default must never be what a seeded flag resolves to"
"""The default value handed to every resolver below.

A flag the seeding dropped resolves to it rather than to anything from the file,
which is what the variant and error-code assertions are looking for.
"""


def _resolve_changing(provider: ControllableInMemoryProvider) -> str:
    return provider.resolve_string_details(CHANGING_FLAG_KEY, "unset").value


def test_change_flag_actually_changes_the_resolved_value() -> None:
    """The assumption every configuration-change scenario rests on.

    If ``change_flag`` emitted an event without altering what the provider
    resolves, the scenario would still pass its event assertion and the suite
    would be certifying a signal with nothing behind it.
    """
    control = InProcessControl()
    provider = control.new_provider()
    assert isinstance(provider, ControllableInMemoryProvider)

    before = _resolve_changing(provider)
    control.change_flag()
    after = _resolve_changing(provider)

    assert before != after, "change_flag did not change the resolved value"


def test_change_flag_emits_a_configuration_change_event_naming_the_flag() -> None:
    """The event the scenarios await is the provider's own, and it names the flag."""
    control = InProcessControl()
    provider = control.new_provider()

    seen: list[tuple[ProviderEvent, list[str] | None]] = []

    def record(_provider: object, event: ProviderEvent, details: object) -> None:
        seen.append((event, getattr(details, "flags_changed", None)))

    # attach() is how the SDK registry wires a provider's emitter; doing it by
    # hand keeps this a unit test of the provider rather than of the registry.
    provider.attach(record)
    control.change_flag()

    assert seen, "no event was emitted"
    event, flags_changed = seen[-1]
    assert event is ProviderEvent.PROVIDER_CONFIGURATION_CHANGED
    assert flags_changed == [CHANGING_FLAG_KEY]


def test_change_does_not_leak_into_the_next_scenario() -> None:
    """Scenario isolation.

    A leak here would make the suite order-dependent: a scenario running after
    the configuration-change one would start with ``changing-flag`` already
    flipped, and the failure would look like a provider defect.
    """
    control = InProcessControl()

    first = control.new_provider()
    assert isinstance(first, ControllableInMemoryProvider)
    baseline = _resolve_changing(first)

    control.change_flag()
    assert _resolve_changing(first) != baseline, (
        "precondition: change_flag had no effect"
    )

    control.prepare_scenario()

    second = control.new_provider()
    assert isinstance(second, ControllableInMemoryProvider)
    assert _resolve_changing(second) == baseline, (
        "the next scenario did not start from the baseline"
    )


def test_change_flag_without_a_provider_fails_clearly() -> None:
    """In-process the flag store and the provider are the same object, so there is
    nothing to change before one exists. Saying so beats an AttributeError."""
    control = InProcessControl()
    with pytest.raises(RuntimeError, match="must create one"):
        control.change_flag()


def test_in_process_control_does_not_pretend_to_have_a_connection() -> None:
    """The load-bearing one.

    A no-op ``disconnect`` would report the ``@stale`` scenarios as passed
    against a provider that cannot go stale -- precisely the silent-green
    failure a conformance suite must never have. ``InProcessControl`` therefore
    does not implement ``ConnectionControl`` at all, and the TCK turns that into
    a skip with a reason.
    """
    assert not isinstance(InProcessControl(), ConnectionControl), (
        "InProcessControl implements ConnectionControl: an in-memory provider has no "
        "connection to lose, and a no-op implementation would make the @stale "
        "scenarios pass without testing anything"
    )


def test_canonical_flag_set_omits_missing_flag() -> None:
    """The property the FLAG_NOT_FOUND scenario depends on.

    Seeding ``missing-flag`` would turn that scenario green for the wrong
    reason, and nothing else in the suite would notice.
    """
    assert "missing-flag" not in canonical_flag_set()


def _flag_type_of(value: typing.Any) -> FlagType:
    """The type a scenario would request a flag of this value as.

    ``bool`` first, because Python makes it a subclass of ``int`` and would
    otherwise route ``boolean-zero-flag`` through the integer accessor.
    """
    if isinstance(value, bool):
        return FlagType.BOOLEAN
    if isinstance(value, int):
        return FlagType.INTEGER
    if isinstance(value, float):
        return FlagType.FLOAT
    if isinstance(value, str):
        return FlagType.STRING
    return FlagType.OBJECT


def test_every_packaged_flag_resolves_to_its_packaged_default_variant() -> None:
    """The whole of what seeding from the file has to achieve.

    Every flag the packaged ``canonical-flags.json`` defines is served, under
    the variant name the file gives as its ``defaultVariant``, with that
    variant's value -- read back through the same typed resolver a scenario
    would use, and compared the way the ``Then`` steps compare.

    Asserting the variant and the absence of an error code is what makes this
    more than an equality check: a flag the seeding dropped resolves to the
    default value with no variant and ``FLAG_NOT_FOUND``, and for the falsy
    flags that fallback value can equal what was expected.
    """
    canonical = json.loads(canonical_flags_json())["flags"]
    provider = ControllableInMemoryProvider(canonical_flag_set())

    # Annotated explicitly, as in the evaluation step: the five typed resolvers
    # have different signatures, so an unannotated mapping infers a value type
    # mypy will not let us call.
    resolvers: dict[FlagType, Callable[[str, typing.Any], typing.Any]] = {
        FlagType.BOOLEAN: provider.resolve_boolean_details,
        FlagType.STRING: provider.resolve_string_details,
        FlagType.INTEGER: provider.resolve_integer_details,
        FlagType.FLOAT: provider.resolve_float_details,
        FlagType.OBJECT: provider.resolve_object_details,
    }

    assert canonical, "the packaged flag file defines no flags"
    for key, definition in canonical.items():
        variant = definition["defaultVariant"]
        expected = definition["variants"][variant]

        details = resolvers[_flag_type_of(expected)](key, _NOT_SEEDED)

        assert details.error_code is None, f"{key}: {details.error_message}"
        assert details.variant == variant, key
        assert details.reason == Reason.STATIC, key
        assert values_equal(expected, details.value), (
            f"{key}/{variant}: packaged {describe(expected)}, "
            f"resolved {describe(details.value)}"
        )


# The variants whose Python *type* the scenarios depend on, and what that type
# and value have to be. Not a second copy of the flag set: every key, variant
# and value in it is already checked against the file by the test above, and
# these rows say the one thing a comparison with the file cannot -- that a
# decoder has not normalised a number on its way through. `10 == 10.0` and
# `0 == False` in Python, so the integral float and the falsy values compare
# equal to exactly the mistranslations they exist to catch.
_LOAD_BEARING: tuple[tuple[str, str, type, typing.Any], ...] = (
    ("integer-flag", "ten", int, 10),
    ("float-flag", "half", float, 0.5),
    ("large-integer-flag", "max-int32", int, 2147483647),
    # 2^53 - 1. A Python int is arbitrary-precision, so being an int is being
    # exact; arriving as a float would round it.
    ("huge-integer-flag", "max-safe", int, 9007199254740991),
    # The trailing .0 is the whole point: as an int, the lossless half of
    # @numeric-coercion passes without coercing anything. This is the row that
    # bit Java.
    ("integral-float-flag", "ten", float, 10.0),
    ("boolean-zero-flag", "zero", bool, False),
    ("integer-zero-flag", "zero", int, 0),
    ("string-zero-flag", "zero", str, ""),
)


@pytest.mark.parametrize(("key", "variant", "expected_type", "expected"), _LOAD_BEARING)
def test_the_decoded_flag_keeps_the_python_type_the_file_wrote(
    key: str, variant: str, expected_type: type, expected: typing.Any
) -> None:
    """A number keeps the type it was written with, stated independently of the file."""
    value = canonical_flag_set()[key].variants[variant]

    assert type(value) is expected_type, (
        f"{key}/{variant} decoded to {describe(value)}, expected an "
        f"{expected_type.__name__}"
    )
    assert value == expected, f"{key}/{variant} decoded to {describe(value)}"


def test_a_number_inside_an_object_keeps_its_type_too() -> None:
    """A structured flag has to decode the same way on both sides of a comparison.

    ``object-flag``'s expected value reaches the assertion through
    ``json.loads`` of the Gherkin table cell. The seeded value reaches it
    through ``json.loads`` of the flag file, and nothing converts either, so a
    member of the object is the same Python type in both.
    """
    template = canonical_flag_set()["object-flag"].variants["template"]

    assert isinstance(template, dict)
    assert type(template["imagesPerPage"]) is int, describe(template["imagesPerPage"])
    assert template["imagesPerPage"] == 100


def test_no_packaged_flag_carries_targeting() -> None:
    """Every scenario expects reason ``STATIC``.

    The TCK tests a provider's mapping of a response, not a backend's
    evaluation logic, so a flag that evaluated its context would report
    ``TARGETING_MATCH`` and fail scenarios that are about something else.
    """
    for key, flag in canonical_flag_set().items():
        assert flag.context_evaluator is None, f"{key} has targeting"


def test_the_hand_built_changing_flag_matches_the_file() -> None:
    """``change_flag`` rebuilds ``changing-flag`` at its other variant.

    That one flag is therefore built by hand rather than decoded, and it names
    both variants itself. The file has to define exactly those two, or flipping
    between them either changes nothing or invents a variant the backend under
    test does not have.
    """
    from_file = canonical_flag_set()[CHANGING_FLAG_KEY]
    hand_built = changing_flag(from_file.default_variant)

    assert hand_built.variants == from_file.variants
    assert from_file.default_variant in hand_built.variants


# A document exercising every level a $comment can appear at, including the one
# level it must not be stripped from.
_COMMENTED_DOCUMENT = json.dumps(
    {
        "$comment": "prose about the document",
        "flags": {
            "structured-flag": {
                "$comment": "prose about the flag",
                "state": "ENABLED",
                "variants": {
                    "$comment": "prose about the variants",
                    "on": {"$comment": "a member of the value, not prose"},
                },
                "defaultVariant": "on",
            }
        },
    }
)


def test_a_comment_is_prose_at_the_document_flag_and_variant_levels() -> None:
    """``$comment`` is how the specification's assets carry prose.

    A loader that took one for a flag, or for a variant, would serve a flag
    nothing asked for and offer a variant no scenario can resolve.
    """
    flags = _decode_canonical_flags(_COMMENTED_DOCUMENT)

    assert set(flags) == {"structured-flag"}
    assert set(flags["structured-flag"].variants) == {"on"}


def test_a_comment_inside_a_variant_value_is_part_of_the_value() -> None:
    """The line the other languages drew deliberately.

    A variant's value is opaque data. An object flag with a ``$comment`` member
    is a perfectly good object flag, and a loader that reached into the value to
    strip it would serve an object no scenario expects -- silently, because the
    rest of the object still matches.
    """
    value = _decode_canonical_flags(_COMMENTED_DOCUMENT)["structured-flag"].variants[
        "on"
    ]

    assert value == {"$comment": "a member of the value, not prose"}


@pytest.mark.parametrize(
    ("document", "message"),
    [
        ("[]", "not a JSON object"),
        ('{"flags": {}}', "defines no flags"),
        ('{"flags": {"a": []}}', "expected an object"),
        ('{"flags": {"a": {"state": "ENABLED"}}}', "variants is not an object"),
        (
            '{"flags": {"a": {"state": "ENABLED", "variants": {"on": 1}, '
            '"defaultVariant": "off"}}}',
            "is not one of its variants",
        ),
        (
            '{"flags": {"a": {"state": "PARTLY", "variants": {"on": 1}, '
            '"defaultVariant": "on"}}}',
            "is none of",
        ),
    ],
)
def test_a_flag_file_this_decoder_does_not_understand_is_refused(
    document: str, message: str
) -> None:
    """Unreachable for a pinned spec revision, and it says which flag if it happens.

    The assets are copied in from the submodule at build time, so a failure here
    means the pinned assets and this decoder disagree about the file's shape --
    which moving the pin should have surfaced. Refusing beats seeding a flag set
    that is quietly missing a flag.
    """
    with pytest.raises(ValueError, match=message):
        _decode_canonical_flags(document)


def test_update_flags_names_the_union_of_old_and_new_keys() -> None:
    """Appendix A asks for the union, not just the new keys.

    A consumer caching evaluations needs to know everything that might have
    changed, and a key that disappeared has changed as much as one that arrived.
    """
    provider = ControllableInMemoryProvider(canonical_flag_set())

    seen: list[list[str] | None] = []
    provider.attach(lambda _p, _e, details: seen.append(details.flags_changed))

    provider.update_flags({})

    assert seen, "no event was emitted"
    assert seen[-1] is not None
    assert set(seen[-1]) == set(canonical_flag_set()), (
        "the event did not name every flag that disappeared"
    )
