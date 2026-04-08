import typing

from pytest_bdd import given, parsers, then, when

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import OpenFeatureError, TypeMismatchError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason

from ..utils import JsonPrimitive, type_cast


@given(
    parsers.cfparse(
        'a {type_info}-flag with key "{key}" and a fallback value "{default}"'
    ),
    target_fixture="key_and_default_and_type",
)
def setup_key_and_default(
    key: str, default: str, type_info: str
) -> tuple:
    return key, default, type_info


@given(
    parsers.cfparse(
        'a {type_info}-flag with key "{key}" and a fallback value ""'
    ),
    target_fixture="key_and_default_and_type",
)
def setup_key_and_empty_default(
    key: str, type_info: str
) -> tuple:
    return key, "", type_info


@when("the flag was evaluated with details", target_fixture="details")
def evaluate_with_details(
    evaluator,
    key_and_default_and_type: tuple,
    evaluation_context: EvaluationContext,
) -> FlagResolutionDetails:
    key, default, type_info = key_and_default_and_type
    default_value = type_cast[type_info](default)
    try:
        if type_info == "Boolean":
            return evaluator.resolve_boolean_value(key, default_value, evaluation_context)
        elif type_info == "String":
            return evaluator.resolve_string_value(key, default_value, evaluation_context)
        elif type_info == "Integer":
            return evaluator.resolve_integer_value(key, default_value, evaluation_context)
        elif type_info == "Float":
            return evaluator.resolve_float_value(key, default_value, evaluation_context)
        elif type_info == "Object":
            return evaluator.resolve_object_value(key, default_value, evaluation_context)
    except TypeMismatchError:
        return FlagResolutionDetails(
            default_value,
            error_code="TYPE_MISMATCH",
            reason=Reason.ERROR,
        )
    except OpenFeatureError as e:
        return FlagResolutionDetails(
            default_value,
            error_code=e.error_code.value if e.error_code else None,
            reason=Reason.ERROR,
        )
    raise AssertionError("no valid type")


@then(
    parsers.cfparse('the resolved details value should be ""'),
)
def resolve_details_value_empty(
    details: FlagResolutionDetails,
    key_and_default_and_type: tuple,
):
    resolve_details_value(details, key_and_default_and_type, "")


@then(
    parsers.cfparse('the resolved details value should be "{value}"'),
)
def resolve_details_value(
    details: FlagResolutionDetails,
    key_and_default_and_type: tuple,
    value: str,
):
    _, _, type_info = key_and_default_and_type
    assert details.value == type_cast[type_info](value)


@then(
    parsers.cfparse('the variant should be "{variant}"'),
)
def resolve_details_variant(
    details: FlagResolutionDetails,
    variant: str,
):
    assert details.variant == variant


@then(
    parsers.cfparse('the reason should be "{reason}"'),
)
def resolve_details_reason(
    details: FlagResolutionDetails,
    reason: str,
):
    assert details.reason == Reason(reason)


@then(
    parsers.cfparse('the error-code should be "{error_code}"'),
)
def resolve_details_error_code(
    details: FlagResolutionDetails,
    error_code: str,
):
    assert details.error_code == error_code


@then(
    parsers.cfparse('the error-code should be ""'),
)
def resolve_details_empty_error_code(
    details: FlagResolutionDetails,
):
    assert details.error_code is None


@then(parsers.cfparse("the resolved metadata should contain"))
def metadata_contains(details: FlagResolutionDetails, datatable):
    assert len(details.flag_metadata) == len(datatable) - 1  # skip header row
    for i in range(1, len(datatable)):
        key, metadata_type, expected = datatable[i]
        assert details.flag_metadata[key] == type_cast[metadata_type](expected)


@then("the resolved metadata is empty")
def empty_metadata(details: FlagResolutionDetails):
    assert len(details.flag_metadata) == 0
