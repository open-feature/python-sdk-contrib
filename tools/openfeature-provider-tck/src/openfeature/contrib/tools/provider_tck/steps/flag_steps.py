"""Steps that declare, evaluate and assert flags."""

from __future__ import annotations

import typing
from collections.abc import Callable

from pytest_bdd import given, parsers, then, when

from openfeature.flag_evaluation import FlagType

from ..state import EvaluationRecord, TckState
from ..values import describe, parse_flag_type, parse_value, values_equal

__all__ = [
    "a_flag_with_key_and_default",
    "no_exception_should_have_been_thrown",
    "the_error_code_should_be",
    "the_flag_was_evaluated_with_details",
    "the_flag_was_modified",
    "the_reason_should_be",
    "the_resolved_object_value_should_contain",
    "the_resolved_value_is_remembered",
    "the_resolved_value_should_be",
    "the_resolved_value_should_have_changed",
    "the_variant_should_be",
]


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


@when("the flag was evaluated with details")
def the_flag_was_evaluated_with_details(tck_state: TckState) -> None:
    """Resolve the declared flag through the typed client call matching its type."""
    client = tck_state.require_client()
    key, flag_type, default = tck_state.require_flag()

    # Annotated explicitly: the five typed getters have different signatures, so
    # an unannotated mapping infers a value type mypy will not let us call.
    calls: dict[FlagType, Callable[[str, typing.Any], typing.Any]] = {
        FlagType.BOOLEAN: client.get_boolean_details,
        FlagType.STRING: client.get_string_details,
        FlagType.INTEGER: client.get_integer_details,
        FlagType.FLOAT: client.get_float_details,
        FlagType.OBJECT: client.get_object_details,
    }

    record = EvaluationRecord()
    try:
        details = calls[flag_type](key, default)
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
    record = tck_state.require_evaluation()
    if record.variant != expected:
        msg = (
            f"variant was {record.variant!r}, expected {expected!r}. A variant that "
            f"does not survive the trip from the backend is one of the easiest parts "
            f"of the contract to drop"
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

    The empty case matters as much as the populated ones. A provider that
    reports a plausible value with no error code is the failure mode the suite
    is most concerned with, because the application has no way to notice.
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


@then("no exception should have been thrown")
def no_exception_should_have_been_thrown(tck_state: TckState) -> None:
    """Assert the evaluation returned rather than raised.

    In Python an errored evaluation returns the code default in the details and
    does not raise, so this holds on the error paths too. A provider that raises
    instead takes the calling application down with it, which is what the
    feature files forbid.
    """
    record = tck_state.require_evaluation()
    if record.raised is not None:
        msg = (
            f"the evaluation raised {record.raised!r}. A flag evaluation must always "
            f"return a value and an error code, never raise"
        )
        raise AssertionError(msg)


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
        wanted = parse_value(parse_flag_type(raw_type), raw_value)
        if key not in record.value:
            msg = f"resolved object value has no member {key!r}"
            raise AssertionError(msg)
        actual = record.value[key]
        if not values_equal(wanted, actual):
            msg = f"object member {key!r} was {describe(actual)}, expected {describe(wanted)}"
            raise AssertionError(msg)


@when("the resolved value is remembered")
def the_resolved_value_is_remembered(tck_state: TckState) -> None:
    """Store the current value so a later step can assert it changed."""
    record = tck_state.require_evaluation()
    tck_state.remembered = record.value
    tck_state.has_memory = True


@then("the resolved details value should have changed")
def the_resolved_value_should_have_changed(tck_state: TckState) -> None:
    """Assert that re-evaluation produced a different value.

    This is the half of the configuration-change contract providers actually get
    wrong. Emitting ``PROVIDER_CONFIGURATION_CHANGED`` and then continuing to
    resolve the old value is worse than emitting nothing, because the
    application acted on a signal that was not true.
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
