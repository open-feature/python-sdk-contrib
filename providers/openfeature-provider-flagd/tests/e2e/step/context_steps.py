import typing

import pytest
from pytest_bdd import given, parsers, when
from tests.e2e.parsers import to_bool, to_list

from openfeature.evaluation_context import EvaluationContext

from ._utils import type_cast


@pytest.fixture
def evaluation_context() -> EvaluationContext:
    return EvaluationContext()


@given(
    parsers.cfparse(
        'a context containing a targeting key with value "{targeting_key}"'
    ),
)
def assign_targeting_context(evaluation_context: EvaluationContext, targeting_key: str):
    """a context containing a targeting key with value <targeting key>."""
    evaluation_context.targeting_key = targeting_key


@given(
    parsers.cfparse(
        'a context containing a key "{key}", with type "{type_info}" and with value "{value}"'
    ),
)
def update_context(
    evaluation_context: EvaluationContext, key: str, type_info: str, value: str
):
    """a context containing a key and value."""
    evaluation_context.attributes[key] = type_cast[type_info](value)


@when(
    parsers.cfparse(
        'context contains keys {fields:s} with values "{svalue}", "{svalue2}", {ivalue:d}, "{bvalue:bool}"',
        extra_types={"bool": to_bool, "s": to_list},
    ),
)
def assign_targeting_context_2(
    evaluation_context: EvaluationContext,
    fields: list,
    svalue: str,
    svalue2: str,
    ivalue: int,
    bvalue: bool,
):
    evaluation_context.attributes[fields[0]] = svalue
    evaluation_context.attributes[fields[1]] = svalue2
    evaluation_context.attributes[fields[2]] = ivalue
    evaluation_context.attributes[fields[3]] = bvalue


@given(
    parsers.cfparse(
        'a context containing a nested property with outer key "{outer}" and inner key "{inner}", with value "{value}"'
    ),
)
def update_context_nested(
    evaluation_context: EvaluationContext,
    outer: str,
    inner: str,
    value: typing.Union[str, int],
):
    """a context containing a nested property with outer key, and inner key, and value."""
    if outer not in evaluation_context.attributes:
        evaluation_context.attributes[outer] = {}
    evaluation_context.attributes[outer][inner] = value
