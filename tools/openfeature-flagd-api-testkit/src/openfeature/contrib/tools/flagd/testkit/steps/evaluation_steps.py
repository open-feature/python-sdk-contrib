import typing

from pytest_bdd import given, parsers, then, when

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ErrorCode, OpenFeatureError, TypeMismatchError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason

from ..utils import type_cast


@given(
    parsers.cfparse(
        'a {type_info}-flag with key "{key}" and a fallback value "{default}"'
    ),
    target_fixture="key_and_default_and_type",
)
def setup_key_and_default(key: str, default: str, type_info: str) -> tuple:
    return key, default, type_info


@given(
    parsers.cfparse('a {type_info}-flag with key "{key}" and a fallback value ""'),
    target_fixture="key_and_default_and_type",
)
def setup_key_and_empty_default(key: str, type_info: str) -> tuple:
    return key, "", type_info


@when("the flag was evaluated with details", target_fixture="details")
def evaluate_with_details(
    evaluator: typing.Any,
    key_and_default_and_type: tuple,
    evaluation_context: EvaluationContext,
) -> FlagResolutionDetails[typing.Any]:
    key, default, type_info = key_and_default_and_type
    default_value = type_cast[type_info](default)
    try:
        result: FlagResolutionDetails[typing.Any]
        if type_info == "Boolean":
            result = evaluator.resolve_boolean_value(
                key, default_value, evaluation_context
            )
        elif type_info == "String":
            result = evaluator.resolve_string_value(
                key, default_value, evaluation_context
            )
        elif type_info == "Integer":
            result = evaluator.resolve_integer_value(
                key, default_value, evaluation_context
            )
        elif type_info == "Float":
            result = evaluator.resolve_float_value(
                key, default_value, evaluation_context
            )
        elif type_info == "Object":
            result = evaluator.resolve_object_value(
                key, default_value, evaluation_context
            )
        else:
            raise AssertionError("no valid type")
        return result
    except TypeMismatchError:
        return FlagResolutionDetails(
            default_value,
            error_code=ErrorCode.TYPE_MISMATCH,
            reason=Reason.ERROR,
        )
    except OpenFeatureError as e:
        return FlagResolutionDetails(
            default_value,
            error_code=e.error_code or None,
            reason=Reason.ERROR,
        )


@then(
    parsers.cfparse('the resolved details value should be ""'),
)
def resolve_details_value_empty(
    details: FlagResolutionDetails[typing.Any],
    key_and_default_and_type: tuple,
) -> None:
    resolve_details_value(details, key_and_default_and_type, "")


@then(
    parsers.cfparse('the resolved details value should be "{value}"'),
)
def resolve_details_value(
    details: FlagResolutionDetails[typing.Any],
    key_and_default_and_type: tuple,
    value: str,
) -> None:
    _, _, type_info = key_and_default_and_type
    assert details.value == type_cast[type_info](value)


@then(
    parsers.cfparse('the variant should be "{variant}"'),
)
def resolve_details_variant(
    details: FlagResolutionDetails[typing.Any],
    variant: str,
) -> None:
    assert details.variant == variant


@then(
    parsers.cfparse('the reason should be "{reason}"'),
)
def resolve_details_reason(
    details: FlagResolutionDetails[typing.Any],
    reason: str,
) -> None:
    assert details.reason == Reason(reason)


@then(
    parsers.cfparse('the error-code should be "{error_code}"'),
)
def resolve_details_error_code(
    details: FlagResolutionDetails[typing.Any],
    error_code: str,
) -> None:
    assert details.error_code == error_code


@then(
    parsers.cfparse('the error-code should be ""'),
)
def resolve_details_empty_error_code(
    details: FlagResolutionDetails[typing.Any],
) -> None:
    assert details.error_code is None


@then(parsers.cfparse("the resolved metadata should contain"))
def metadata_contains(
    details: FlagResolutionDetails[typing.Any], datatable: list[list[str]]
) -> None:
    assert len(details.flag_metadata) == len(datatable) - 1  # skip header row
    for i in range(1, len(datatable)):
        key, metadata_type, expected = datatable[i]
        assert details.flag_metadata[key] == type_cast[metadata_type](expected)


@then("the resolved metadata is empty")
def empty_metadata(details: FlagResolutionDetails[typing.Any]) -> None:
    assert len(details.flag_metadata) == 0
