from __future__ import annotations

import time
import typing

from flagd_evaluator import evaluate_targeting
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import ParseError


def targeting(
    key: str,
    targeting: dict,
    evaluation_context: typing.Optional[EvaluationContext] = None,
) -> typing.Any:
    """
    Evaluate targeting rules using the native flagd-evaluator.

    This uses the Rust-based evaluator which includes all custom operators:
    - fractional: A/B testing with consistent hashing
    - sem_ver: Semantic version comparison
    - starts_with: String prefix matching
    - ends_with: String suffix matching
    """
    if not isinstance(targeting, dict):
        raise ParseError(f"Invalid 'targeting' value in flag: {targeting}")

    # Build evaluation context matching flagd spec
    json_logic_context: dict[str, typing.Any] = (
        dict(evaluation_context.attributes) if evaluation_context else {}
    )
    json_logic_context["$flagd"] = {"flagKey": key, "timestamp": int(time.time())}
    json_logic_context["targetingKey"] = (
        evaluation_context.targeting_key if evaluation_context else None
    )

    # Use native evaluator
    result = evaluate_targeting(targeting, json_logic_context)

    if not result["success"]:
        raise ParseError(f"Targeting evaluation failed: {result.get('error')}")

    return result["result"]
