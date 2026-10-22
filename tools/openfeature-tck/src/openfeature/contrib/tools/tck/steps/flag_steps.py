"""Steps that declare, evaluate and assert flags."""

from __future__ import annotations

import typing
from collections.abc import Callable

from pytest_bdd import given, parsers, then, when

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagMetadata, FlagType

from ..capability import Capability
from ..state import EvaluationRecord, TckState
from ..values import (
    describe,
    parse_flag_type,
    parse_table_value,
    parse_value,
    values_equal,
)

__all__ = [
    "a_context_containing_a_targeting_key",
    "a_context_with_the_following_keys",
    "a_flag_with_key_and_default",
    "no_exception_should_have_been_thrown",
    "the_error_code_should_be",
    "the_error_message_should_be_empty",
    "the_flag_was_evaluated_with_details",
    "the_flag_was_modified",
    "the_reason_should_be",
    "the_resolved_metadata_is_empty",
    "the_resolved_metadata_should_contain",
    "the_resolved_object_value_should_contain",
    "the_resolved_value_is_remembered",
    "the_resolved_value_should_be",
    "the_resolved_value_should_have_changed",
    "the_variant_should_be",
]

_TARGETING_KEY_COLUMN = "targetingKey"
"""The key a context table row uses to set the targeting key rather than an attribute.

The specification's own spelling for the field, so a table can state every part
of a context in one place instead of needing a second step for the one entry
that is not an attribute.
"""

_METADATA_TYPES: dict[str, type | tuple[type, ...]] = {
    "String": str,
    "Boolean": bool,
    "Integer": int,
    "Float": float,
}
"""What a ``metadata_type`` names, and what the resolved entry must therefore be.

Flag metadata is typed in the specification as a map of primitives, and the
column exists so a scenario can say which one it expects: a provider that sends
``"2"`` where the table says ``Integer`` has lost the type on the way, and a
comparison that coerced would not notice.
"""


@given(
    parsers.re(
        r'^an? (?P<flag_type>[A-Za-z]+)-flag with key "(?P<key>[^"]*)" '
        r'and a default value "(?P<default>[^"]*)"$'
    )
)
def a_flag_with_key_and_default(
    tck_state: TckState, flag_type: str, key: str, default: str
) -> None:
    """Declare the flag the scenario is about, and the type it is requested as.

    The two are independent on purpose: most of ``errors.feature`` asks for a
    flag as a type it is not.
    """
    parsed_type = parse_flag_type(flag_type)
    tck_state.flag_key = key
    tck_state.flag_type = parsed_type
    tck_state.default_value = parse_value(parsed_type, default)


@given(
    parsers.re(r'^a context containing a targeting key with value "(?P<value>[^"]*)"$')
)
def a_context_containing_a_targeting_key(tck_state: TckState, value: str) -> None:
    """Supply the evaluation context the resolve call is made with.

    The wording is `Appendix B
    <https://github.com/open-feature/spec/blob/main/specification/assets/gherkin/evaluation.feature>`_'s.

    Only the targeting key: ``targeting-key-flag``'s rule keys on it, so it is
    what the canonical set can observe arriving. A custom attribute would need a
    second flag whose rule keys on one, which Appendix F lists as a known gap.
    """
    context = tck_state.evaluation_context
    if context is None:
        tck_state.evaluation_context = EvaluationContext(targeting_key=value)
    else:
        context.targeting_key = value


@given("a context with the following keys:")
def a_context_with_the_following_keys(
    tck_state: TckState, datatable: list[list[str]]
) -> None:
    """Supply several typed context entries at once.

    The table form of the step above, for a scenario whose targeting depends on
    more than one key. Its type vocabulary is
    :data:`~..values.TABLE_TYPE_NAMES`, wider than a flag declaration's, because
    a table is where a scenario reaches for the types a targeting operator takes.

    The context is rebuilt rather than mutated -- ``EvaluationContext.attributes``
    is typed as a :class:`~collections.abc.Mapping` -- and rebuilding is where a
    statement can be lost. So entries from an earlier step survive a table that
    says nothing about them, and a ``targetingKey`` row is the later statement
    about the targeting key and wins.
    """
    header, *rows = datatable
    if header != ["key", "type", "value"]:
        msg = f"expected a data table with columns key, type, value; got {header}"
        raise AssertionError(msg)

    context = tck_state.evaluation_context or EvaluationContext()
    attributes = dict(context.attributes)
    targeting_key = context.targeting_key

    for key, raw_type, raw_value in rows:
        value = parse_table_value(raw_type, raw_value)
        if key == _TARGETING_KEY_COLUMN:
            targeting_key = str(value)
        else:
            attributes[key] = value

    tck_state.evaluation_context = EvaluationContext(
        targeting_key=targeting_key, attributes=attributes
    )


@when("the flag was evaluated with details")
def the_flag_was_evaluated_with_details(tck_state: TckState) -> None:
    """Resolve the declared flag through the typed client call matching its type."""
    client = tck_state.require_client()
    key, flag_type, default = tck_state.require_flag()

    # Annotated explicitly: the five typed getters have different signatures, so
    # an unannotated mapping infers a value type mypy will not let us call.
    calls: dict[
        FlagType, Callable[[str, typing.Any, EvaluationContext | None], typing.Any]
    ] = {
        FlagType.BOOLEAN: client.get_boolean_details,
        FlagType.STRING: client.get_string_details,
        FlagType.INTEGER: client.get_integer_details,
        FlagType.FLOAT: client.get_float_details,
        FlagType.OBJECT: client.get_object_details,
    }

    record = EvaluationRecord()
    try:
        # Passed positionally and unconditionally, `None` included: the SDK's own
        # default for the parameter is `None`, so a scenario that declared no
        # context sends what a two-argument call would.
        details = calls[flag_type](key, default, tck_state.evaluation_context)
    except BaseException as exc:  # recorded here, asserted on by its own step
        record.raised = exc
        record.value = default
    else:
        record.value = details.value
        record.variant = details.variant
        record.reason = str(details.reason) if details.reason is not None else None
        record.error_code = (
            details.error_code.value if details.error_code is not None else None
        )
        record.error_message = details.error_message
        record.flag_metadata = details.flag_metadata

    tck_state.last = record


@then(parsers.re(r'^the resolved details value should be "(?P<expected>[^"]*)"$'))
def the_resolved_value_should_be(tck_state: TckState, expected: str) -> None:
    _key, flag_type, _default = tck_state.require_flag()
    record = tck_state.require_evaluation()
    wanted = parse_value(flag_type, expected)

    if not values_equal(wanted, record.value):
        detail = (
            f" (the client also reported: {record.error_message})"
            if record.error_message
            else ""
        )
        msg = (
            f"flag {tck_state.flag_key!r} resolved to {describe(record.value)}, "
            f"expected {describe(wanted)}{detail}"
        )
        raise AssertionError(msg)


@then(parsers.re(r'^the variant should be "(?P<expected>[^"]*)"$'))
def the_variant_should_be(tck_state: TckState, expected: str) -> None:
    """Assert the resolved variant, for an adoption that declared ``@variants``.

    The failure message says which of the two readings applies: a variant lost in
    transit is a defect, while a backend with no variant concept at all should
    withhold the capability rather than fail here.
    """
    record = tck_state.require_evaluation()
    if record.variant != expected:
        msg = (
            f"variant was {record.variant!r}, expected {expected!r}. A variant that "
            f"does not survive the trip from the backend is one of the easiest parts "
            f"of the contract to drop -- but if this backend has no variant concept "
            f"for a plain flag, withhold {Capability.VARIANTS.tag} instead: "
            f"requirement 2.2.4 is a SHOULD and types.md types the field as optional"
        )
        raise AssertionError(msg)


@then(parsers.re(r'^the reason should be "(?P<expected>[^"]*)"$'))
def the_reason_should_be(tck_state: TckState, expected: str) -> None:
    record = tck_state.require_evaluation()
    if record.reason != expected:
        msg = f"reason was {record.reason!r}, expected {expected!r}"
        raise AssertionError(msg)


@then(parsers.re(r'^the error-code should be "(?P<expected>[^"]*)"$'))
def the_error_code_should_be(tck_state: TckState, expected: str) -> None:
    """Assert the reported error code, where the empty string means none at all.

    The empty case matters as much as the populated ones: a provider that reports
    a plausible value with no error code leaves the application no way to notice.
    """
    record = tck_state.require_evaluation()
    actual = record.error_code or ""

    if actual == expected:
        return

    if expected == "":
        msg = f"error-code was {actual!r}, expected none"
    elif actual == "":
        msg = (
            f"no error-code was reported, expected {expected!r}. Returning a value "
            f"without an error code leaves the application unable to tell that "
            f"anything went wrong"
        )
    else:
        msg = f"error-code was {actual!r}, expected {expected!r}"
    raise AssertionError(msg)


@then("the error message should be empty")
def the_error_message_should_be_empty(tck_state: TckState) -> None:
    """Assert no error message was reported (requirement 2.3.2).

    Asserted on the success paths, where a message contradicts the value beside
    it. ``None`` and ``""`` are both "none".
    """
    record = tck_state.require_evaluation()
    if record.error_message:
        msg = (
            f"an error message was reported alongside a successful evaluation: "
            f"{record.error_message!r}. A value and an error message are two "
            f"contradictory signals, and the application cannot tell which to believe"
        )
        raise AssertionError(msg)


@then("no exception should have been thrown")
def no_exception_should_have_been_thrown(tck_state: TckState) -> None:
    """Assert that nothing the scenario asked of the provider raised.

    That is the evaluation, if there was one, and every direct lifecycle call:
    each records what it raised rather than propagating it, and this is the one
    step that reads those records back.

    In Python an errored evaluation returns the code default in the details and
    does not raise, so this holds on the error paths too.
    """
    if not tck_state.has_called_provider():
        msg = (
            "nothing has been asked of the provider in this scenario: a "
            '"When the flag was evaluated with details" or "When the provider is '
            'shut down" step must come first'
        )
        raise AssertionError(msg)

    raised = tck_state.raised()
    if raised:
        what, exc = raised[0]
        msg = (
            f"{what} raised {exc!r}. A provider must return from an evaluation with a "
            f"value and an error code, and from a lifecycle call quietly -- never raise"
        )
        raise AssertionError(msg) from exc


@then("the resolved object value should contain")
def the_resolved_object_value_should_contain(
    tck_state: TckState, datatable: list[list[str]]
) -> None:
    """Assert members of a structured value, each with its own expected type."""
    record = tck_state.require_evaluation()
    header, *rows = datatable

    if header != ["key", "type", "value"]:
        msg = f"expected a data table with columns key, type, value; got {header}"
        raise AssertionError(msg)

    if not isinstance(record.value, dict):
        msg = (
            f"resolved object value is {describe(record.value)}, which has no members "
            f"to check"
        )
        raise AssertionError(msg)

    for key, raw_type, raw_value in rows:
        # The table vocabulary, not a flag declaration's: a structured value can
        # hold a list, and a scenario naming one must not be refused here.
        wanted = parse_table_value(raw_type, raw_value)
        if key not in record.value:
            msg = f"resolved object value has no member {key!r}"
            raise AssertionError(msg)
        actual = record.value[key]
        if not values_equal(wanted, actual):
            msg = f"object member {key!r} was {describe(actual)}, expected {describe(wanted)}"
            raise AssertionError(msg)


@then("the resolved metadata should contain")
def the_resolved_metadata_should_contain(
    tck_state: TckState, datatable: list[list[str]]
) -> None:
    """Assert typed flag-metadata entries on the last evaluation.

    The wording and the columns are the specification's own, from
    ``assets/gherkin/metadata.feature``: flag metadata is spec behaviour rather
    than one vendor's, so the question belongs in the shared vocabulary and not
    in each adoption's glue.

    An entry the table does not list is not checked. A provider is free to carry
    more than a scenario is interested in, and a table that had to name all of it
    would break every time the backend added a field.
    """
    metadata = _require_metadata(tck_state)
    header, *rows = datatable
    if header != ["key", "metadata_type", "value"]:
        msg = (
            f"expected a data table with columns key, metadata_type, value; "
            f"got {header}"
        )
        raise AssertionError(msg)

    for key, raw_type, raw_value in rows:
        wanted = _parse_metadata_value(raw_type, raw_value)
        if key not in metadata:
            msg = (
                f"the resolved metadata has no entry {key!r}; it carries "
                f"{sorted(metadata)}"
            )
            raise AssertionError(msg)

        actual = metadata[key]
        if not _is_metadata_type(raw_type, actual) or not values_equal(wanted, actual):
            msg = (
                f"metadata entry {key!r} ({raw_type}) was {describe(actual)}, "
                f"expected {describe(wanted)}"
            )
            raise AssertionError(msg)


@then("the resolved metadata is empty")
def the_resolved_metadata_is_empty(tck_state: TckState) -> None:
    """Assert the last evaluation carried no flag metadata.

    The other half of the specification's pair, and the one that catches a
    provider inventing entries: a scenario cannot state an absence by listing
    nothing, because an unlisted entry is deliberately not checked.
    """
    metadata = _require_metadata(tck_state)
    if metadata:
        msg = (
            f"the resolved metadata carries {dict(metadata)!r}, expected none. "
            f"Metadata a backend did not send is metadata an application cannot "
            f"act on"
        )
        raise AssertionError(msg)


def _require_metadata(tck_state: TckState) -> FlagMetadata:
    """The flag metadata of the last evaluation, or a clear failure.

    ``None`` is refused rather than read as empty: the specification types the
    field as a map, and a provider that answers with nothing at all is a
    different finding from one that answers with no entries.
    """
    record = tck_state.require_evaluation()
    if record.flag_metadata is None:
        msg = (
            "the evaluation details carried no flag metadata at all, expected a "
            "map. An absent map and an empty one are not the same answer, and only "
            "the empty one is what a flag without metadata resolves to"
        )
        raise AssertionError(msg)
    return record.flag_metadata


def _parse_metadata_value(type_name: str, raw: str) -> typing.Any:
    """Convert an expected metadata value, refusing a type metadata cannot carry."""
    if type_name not in _METADATA_TYPES:
        names = ", ".join(_METADATA_TYPES)
        msg = (
            f"unknown metadata type {type_name!r}: flag metadata is {names}. A "
            f"structured value cannot travel in metadata, so a table asking for "
            f"one is asking the wrong question"
        )
        raise ValueError(msg)
    return parse_table_value(type_name, raw)


def _is_metadata_type(type_name: str, value: typing.Any) -> bool:
    """Whether a resolved entry is of the type its row declared.

    ``bool`` is excluded from ``Integer`` and ``Float`` explicitly, because
    Python makes it a subclass of ``int``: without that, a provider sending
    ``True`` would satisfy a row asking for ``1``.
    """
    wanted = _METADATA_TYPES[type_name]
    if wanted is bool:
        return isinstance(value, bool)
    return isinstance(value, wanted) and not isinstance(value, bool)


@when("the resolved value is remembered")
def the_resolved_value_is_remembered(tck_state: TckState) -> None:
    """Store the current value so a later step can assert it changed."""
    record = tck_state.require_evaluation()
    tck_state.remembered = record.value
    tck_state.has_memory = True


@then("the resolved details value should have changed")
def the_resolved_value_should_have_changed(tck_state: TckState) -> None:
    """Assert that re-evaluation produced a different value.

    Emitting ``PROVIDER_CONFIGURATION_CHANGED`` and then continuing to resolve
    the old value is worse than emitting nothing, because the application acted
    on a signal that was not true.
    """
    record = tck_state.require_evaluation()
    if not tck_state.has_memory:
        msg = (
            "no value was remembered in this scenario: a "
            '"the resolved value is remembered" step must come first'
        )
        raise AssertionError(msg)

    if values_equal(tck_state.remembered, record.value):
        msg = (
            f"the resolved value is still {describe(record.value)} after the "
            f"configuration changed. The change was signalled but not applied, so the "
            f"event told the application something untrue"
        )
        raise AssertionError(msg)


@when("the flag was modified")
def the_flag_was_modified(tck_state: TckState) -> None:
    """Change flag configuration on the backend."""
    control = tck_state.config.control
    try:
        control.change_flag()
    except Exception as exc:
        msg = f"could not change flag configuration on {control.description}: {exc}"
        raise AssertionError(msg) from exc
