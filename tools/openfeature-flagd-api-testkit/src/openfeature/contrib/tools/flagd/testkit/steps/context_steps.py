import pytest
from pytest_bdd import given, parsers

from openfeature.evaluation_context import EvaluationContext

from ..utils import type_cast


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@given(
    parsers.cfparse(
        'a context containing a targeting key with value "{targeting_key}"'
    ),
)
def assign_targeting_context(evaluation_context: EvaluationContext, targeting_key: str):
    evaluation_context.targeting_key = targeting_key


@given(
    parsers.cfparse(
        'a context containing a key "{key}", with type "{type_info}" and with value "{value}"'
    ),
)
def update_context(
    evaluation_context: EvaluationContext, key: str, type_info: str, value: str
):
    evaluation_context.attributes[key] = type_cast[type_info](value)


@given(
    parsers.cfparse(
        'a context containing a key "{key}", with type "{type_info}" and with value ""'
    ),
)
def update_context_without_value(
    evaluation_context: EvaluationContext, key: str, type_info: str
):
    update_context(evaluation_context, key, type_info, "")


@given(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value "{value}"'
    ),
)
def update_context_nested(
    evaluation_context: EvaluationContext,
    outer: str,
    inner: str,
    value: str | int,
):
    if outer not in evaluation_context.attributes:
        evaluation_context.attributes[outer] = {}
    evaluation_context.attributes[outer][inner] = value
