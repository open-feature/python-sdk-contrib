import typing

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
def assign_targeting_context(
    evaluation_context: EvaluationContext, targeting_key: str
) -> None:
    evaluation_context.targeting_key = targeting_key


@given(
    parsers.cfparse(
        'a context containing a key "{key}", with type "{type_info}" and with value "{value}"'
    ),
)
def update_context(
    evaluation_context: EvaluationContext, key: str, type_info: str, value: str
) -> None:
    attrs = typing.cast(dict, evaluation_context.attributes)
    attrs[key] = type_cast[type_info](value)


@given(
    parsers.cfparse(
        'a context containing a key "{key}", with type "{type_info}" and with value ""'
    ),
)
def update_context_without_value(
    evaluation_context: EvaluationContext, key: str, type_info: str
) -> None:
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
) -> None:
    attrs = typing.cast(dict, evaluation_context.attributes)
    if outer not in attrs:
        attrs[outer] = {}
    typing.cast(dict, attrs[outer])[inner] = value
