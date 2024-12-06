import time
import typing

from json_logic import builtins, jsonLogic
from json_logic.types import JsonValue

from openfeature.evaluation_context import EvaluationContext

from .custom_ops import (
    ends_with,
    fractional,
    sem_ver,
    starts_with,
)

OPERATORS = {
    **builtins.BUILTINS,
    "fractional": fractional,
    "starts_with": starts_with,
    "ends_with": ends_with,
    "sem_ver": sem_ver,
}


def targeting(
    key: str,
    targeting: dict,
    evaluation_context: typing.Optional[EvaluationContext] = None,
) -> JsonValue:
    json_logic_context = evaluation_context.attributes if evaluation_context else {}
    json_logic_context["$flagd"] = {"flagKey": key, "timestamp": int(time.time())}
    json_logic_context["targetingKey"] = (
        evaluation_context.targeting_key if evaluation_context else None
    )
    return jsonLogic(targeting, json_logic_context, OPERATORS)
