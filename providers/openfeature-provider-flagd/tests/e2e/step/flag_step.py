import requests
from asserts import assert_equal
from pytest_bdd import given, parsers, then, when

from openfeature.client import OpenFeatureClient
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import EventDetails
from openfeature.flag_evaluation import FlagEvaluationDetails, Reason

from ._utils import JsonPrimitive, type_cast


@given(
    parsers.cfparse(
        'a {type_info}-flag with key "{key}" and a default value "{default}"'
    ),
    target_fixture="key_and_default_and_type",
)
def setup_key_and_default(
    key: str, default: JsonPrimitive, type_info: str
) -> tuple[str, JsonPrimitive, str]:
    return key, default, type_info


@when("the flag was evaluated with details", target_fixture="details")
def evaluate_with_details(
    client: OpenFeatureClient,
    key_and_default_and_type: tuple,
    evaluation_context: EvaluationContext,
):
    key, default, type_info = key_and_default_and_type
    default = type_cast[type_info](default)
    if type_info == "Boolean":
        return client.get_boolean_details(key, default, evaluation_context)
    elif type_info == "String":
        return client.get_string_details(key, default, evaluation_context)
    elif type_info == "Integer":
        return client.get_integer_details(key, default, evaluation_context)
    elif type_info == "Float":
        return client.get_float_details(key, default, evaluation_context)
    elif type_info == "Object":
        return client.get_object_details(key, default, evaluation_context)
    raise AssertionError("no valid object type")


@when("the flag was modified")
def assert_flag_change_event(container):
    requests.post(f"{container.get_launchpad_url()}/change", timeout=1)


@then("the flag should be part of the event payload")
def assert_flag_change(key_and_default_and_type: tuple, event_details: EventDetails):
    key, _, _ = key_and_default_and_type
    assert key in event_details.flags_changed


@then(
    parsers.cfparse('the resolved details value should be ""'),
)
def resolve_details_value_string(
    details: FlagEvaluationDetails[JsonPrimitive],
    key_and_default_and_type: tuple,
):
    resolve_details_value(details, key_and_default_and_type, "")


@then(
    parsers.cfparse('the resolved details value should be "{value}"'),
)
def resolve_details_value(
    details: FlagEvaluationDetails[JsonPrimitive],
    key_and_default_and_type: tuple,
    value: str,
):
    _, _, type_info = key_and_default_and_type
    assert_equal(details.value, type_cast[type_info](value))


@then(
    parsers.cfparse('the variant should be "{variant}"'),
)
def resolve_details_variant(
    details: FlagEvaluationDetails[JsonPrimitive],
    variant: str,
):
    assert_equal(details.variant, variant)


@then(
    parsers.cfparse('the reason should be "{reason}"'),
)
def resolve_details_reason(
    details: FlagEvaluationDetails[JsonPrimitive],
    reason: str,
):
    assert_equal(details.reason, Reason(reason))
