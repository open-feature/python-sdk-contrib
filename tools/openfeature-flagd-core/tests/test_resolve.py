import json
import typing

import pytest

from openfeature.contrib.tools.flagd.core import FlagdCore
from openfeature.contrib.tools.flagd.core.targeting.custom_ops import (
    ResolveResult,
    resolve,
)
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import GeneralError, TypeMismatchError
from openfeature.flag_evaluation import Reason

VARIANTS = {
    "red": "#FF0000",
    "blue": "#0000FF",
    "green": "#00FF00",
    "yellow": "#FFFF00",
}


def resolve_flag(targeting: typing.Any, **extra: typing.Any) -> dict:
    return {
        "flags": {
            "color": {
                "state": "ENABLED",
                "defaultVariant": "yellow",
                "variants": VARIANTS,
                "targeting": targeting,
            }
        },
        **extra,
    }


def evaluate(flags: dict, attributes: dict | None = None, flag_key: str = "color"):
    core = FlagdCore()
    core.set_flags(json.dumps(flags))
    return core.resolve_string_value(
        flag_key, "default", EvaluationContext(attributes=attributes or {})
    )


NESTED_BRANCHES = {
    "if": [
        {"==": [{"var": "id"}, "a"]},
        {"resolve": ["red", "ALLOWLIST", [["details", "customer-a"]]]},
        {"==": [{"var": "id"}, "b"]},
        {"resolve": ["red", "SPLIT", [["details", "customer-b"]]]},
        {"resolve": ["blue", "FALLTHROUGH", [["details", "else"]]]},
    ]
}

# variants named "true", "false" and "1", which only a coerced variant can select
COERCED_KEYS = {
    "flags": {
        "coerced": {
            "state": "ENABLED",
            "defaultVariant": "false",
            "variants": {"true": "#00FF00", "false": "#FF0000", "1": "#0000FF"},
        }
    }
}


def coerced_flag(targeting: dict) -> dict:
    flags = json.loads(json.dumps(COERCED_KEYS))
    flags["flags"]["coerced"]["targeting"] = targeting
    return flags


@pytest.mark.parametrize(
    ("flags", "context", "variant", "reason", "metadata"),
    [
        pytest.param(
            resolve_flag({"resolve": ["red"]}),
            None,
            "red",
            Reason.TARGETING_MATCH,
            {},
            id="whole rule keeps targeting match",
        ),
        pytest.param(
            resolve_flag({"resolve": ["blue", "ALLOWLIST"]}),
            None,
            "blue",
            "ALLOWLIST",
            {},
            id="custom reason",
        ),
        # any other reason passes through and doesn't change the value or variant
        *(
            pytest.param(
                resolve_flag({"resolve": ["blue", reason]}),
                None,
                "blue",
                reason,
                {},
                id=f"{reason} reason keeps value and variant",
            )
            for reason in ("SPLIT", "FALLTHROUGH")
        ),
        # every OpenFeature and flagd reason but TARGETING_MATCH and SPLIT is reserved;
        # a rule returning one keeps TARGETING_MATCH
        *(
            pytest.param(
                resolve_flag({"resolve": ["blue", reason_arg, [["details", "kept"]]]}),
                {"reason": reason},
                "blue",
                Reason.TARGETING_MATCH,
                {"details": "kept"},
                id=f"reserved {kind} {reason} reason keeps targeting match",
            )
            for reason in (
                "ERROR",
                "DISABLED",
                "DEFAULT",
                "FALLBACK",
                "STATIC",
                "UNKNOWN",
                "CACHED",
                "STALE",
            )
            for kind, reason_arg in (
                ("literal", reason),
                ("computed", {"var": "reason"}),
            )
        ),
        pytest.param(
            resolve_flag({"resolve": ["green", None, [["details", "pilot"]]]}),
            None,
            "green",
            Reason.TARGETING_MATCH,
            {"details": "pilot"},
            id="null reason keeps targeting match and adds metadata",
        ),
        pytest.param(
            resolve_flag(NESTED_BRANCHES),
            {"id": "a"},
            "red",
            "ALLOWLIST",
            {"details": "customer-a"},
            id="nested if first branch",
        ),
        pytest.param(
            resolve_flag(NESTED_BRANCHES),
            {"id": "b"},
            "red",
            "SPLIT",
            {"details": "customer-b"},
            id="nested if second branch",
        ),
        pytest.param(
            resolve_flag(NESTED_BRANCHES),
            {"id": "z"},
            "blue",
            "FALLTHROUGH",
            {"details": "else"},
            id="nested if else branch",
        ),
        pytest.param(
            resolve_flag({"if": [{"resolve": ["green", "ALLOWLIST"]}]}),
            None,
            "green",
            "ALLOWLIST",
            {},
            id="single if clause",
        ),
        # a fixed bucketing value and zero weights pick the bucket deterministically
        pytest.param(
            resolve_flag(
                {
                    "fractional": [
                        "key",
                        [{"resolve": ["red", "SPLIT", [["details", "treatment"]]]}, 1],
                        [{"resolve": ["blue", "SPLIT", [["details", "holdback"]]]}, 0],
                    ]
                }
            ),
            None,
            "red",
            "SPLIT",
            {"details": "treatment"},
            id="fractional bucket variant",
        ),
        pytest.param(
            resolve_flag(
                {"fractional": ["key", [{"resolve": ["red", "SPLIT"]}, 0], ["blue", 1]]}
            ),
            None,
            "blue",
            Reason.TARGETING_MATCH,
            {},
            id="fractional mixes plain and resolve buckets",
        ),
        pytest.param(
            resolve_flag(
                {
                    "fractional": [
                        "key",
                        [{"resolve": ["red", "SPLIT"]}, 0],
                        [{"cat": ["gr", "een"]}, 1],
                    ]
                }
            ),
            None,
            "green",
            Reason.TARGETING_MATCH,
            {},
            id="fractional computed plain bucket variant",
        ),
        pytest.param(
            resolve_flag(
                {
                    "fractional": [
                        "key",
                        [{"resolve": [{"cat": ["r", "ed"]}, "SPLIT"]}, 1],
                        ["blue", 0],
                    ]
                }
            ),
            None,
            "red",
            "SPLIT",
            {},
            id="fractional resolve with computed variant",
        ),
        pytest.param(
            resolve_flag(
                {
                    "if": [
                        True,
                        {
                            "fractional": [
                                "key",
                                [
                                    {
                                        "resolve": [
                                            "green",
                                            "SPLIT",
                                            [["details", "treatment"]],
                                        ]
                                    },
                                    1,
                                ],
                            ]
                        },
                        "blue",
                    ]
                }
            ),
            None,
            "green",
            "SPLIT",
            {"details": "treatment"},
            id="fractional in an if result",
        ),
        pytest.param(
            resolve_flag(
                {
                    "resolve": [
                        {"if": [True, "red", "blue"]},
                        {"cat": ["ALLOW", "LIST"]},
                        [["details", {"cat": ["us-", {"var": "bucket"}]}]],
                    ]
                }
            ),
            {"bucket": "10pct"},
            "red",
            "ALLOWLIST",
            {"details": "us-10pct"},
            id="computed variant reason and details",
        ),
        pytest.param(
            resolve_flag({"resolve": ["red", None, {"var": "meta"}]}),
            {"meta": [["details", "from-context"]]},
            "red",
            Reason.TARGETING_MATCH,
            {"details": "from-context"},
            id="computed metadata list",
        ),
        pytest.param(
            resolve_flag({"resolve": ["red", None, [{"var": "pair"}]]}),
            {"pair": ["details", "from-context"]},
            "red",
            Reason.TARGETING_MATCH,
            {"details": "from-context"},
            id="computed metadata pair",
        ),
        pytest.param(
            resolve_flag(
                {
                    "resolve": [
                        "red",
                        None,
                        [[{"cat": ["az-", {"var": "zone"}]}, "served"]],
                    ]
                }
            ),
            {"zone": "a"},
            "red",
            Reason.TARGETING_MATCH,
            {"az-a": "served"},
            id="computed metadata key",
        ),
        pytest.param(
            resolve_flag(
                {
                    "resolve": [
                        "red",
                        "SPLIT",
                        [
                            ["percent", 10],
                            ["share", {"/": [{"var": "hits"}, 4]}],
                            ["enabled", False],
                        ],
                    ]
                }
            ),
            {"hits": 1},
            "red",
            "SPLIT",
            {"percent": 10, "share": 0.25, "enabled": False},
            id="numeric and boolean metadata",
        ),
        pytest.param(
            resolve_flag(
                {"$ref": "picked"},
                **{"$evaluators": {"picked": {"resolve": ["blue", "ALLOWLIST"]}}},
            ),
            None,
            "blue",
            "ALLOWLIST",
            {},
            id="shared evaluator",
        ),
        # a multi-key object is literal data to JsonLogic, so a nested "resolve" key is just data
        pytest.param(
            resolve_flag(
                {
                    "if": [
                        {
                            "some": [
                                [{"payload": {"resolve": "eu"}, "tag": 1}],
                                {"==": [{"var": "payload.resolve"}, "eu"]},
                            ]
                        },
                        {"resolve": ["red", "EU"]},
                        "blue",
                    ]
                }
            ),
            None,
            "red",
            "EU",
            {},
            id="literal data keeps a nested resolve key",
        ),
    ],
)
def test_resolve(flags, context, variant, reason, metadata) -> None:
    result = evaluate(flags, context)
    assert result.variant == variant
    assert result.value == VARIANTS[variant]
    assert result.reason == reason
    assert result.error_code is None
    for key, value in metadata.items():
        assert result.flag_metadata[key] == value
        assert type(result.flag_metadata[key]) is type(value)


@pytest.mark.parametrize(
    ("targeting", "context", "variant"),
    [
        pytest.param({"resolve": [True, "BETA"]}, None, "true", id="boolean variant"),
        pytest.param(
            {"resolve": [{"var": "pick"}]}, {"pick": 1}, "1", id="computed number"
        ),
    ],
)
def test_resolve_coerces_variant_like_a_plain_result(
    targeting, context, variant
) -> None:
    result = evaluate(coerced_flag(targeting), context, flag_key="coerced")
    assert result.variant == variant


def test_rule_metadata_wins_over_flag_and_flag_set() -> None:
    flags = resolve_flag(
        {"resolve": ["red", "ALLOWLIST", [["details", "rule"], ["onlyRule", True]]]},
        metadata={"details": "set", "owner": "set", "team": "set"},
    )
    flags["flags"]["color"]["metadata"] = {"details": "flag", "owner": "flag"}
    result = evaluate(flags)
    assert result.flag_metadata == {
        "details": "rule",
        "owner": "flag",
        "team": "set",
        "onlyRule": True,
    }


LITERAL_RESERVED = {
    "resolve": [
        "red",
        None,
        [["flagSetId", "rule"], ["version", "rule"], ["details", "rule"]],
    ]
}
COMPUTED_RESERVED = {
    "resolve": [
        "red",
        None,
        [
            [{"cat": ["flagSet", "Id"]}, "rule"],
            [{"var": "key"}, "rule"],
            ["details", "rule"],
        ],
    ]
}


# flagSetId and version belong to flag set metadata, so rule metadata can't override or add them,
# whether the key is literal or computed
@pytest.mark.parametrize(
    ("targeting", "flag_set_metadata", "expected"),
    [
        pytest.param(
            LITERAL_RESERVED,
            {"flagSetId": "set", "version": "1"},
            {"flagSetId": "set", "version": "1"},
            id="literal keys keep flag set values",
        ),
        pytest.param(
            COMPUTED_RESERVED,
            {"flagSetId": "set", "version": "1"},
            {"flagSetId": "set", "version": "1"},
            id="computed keys keep flag set values",
        ),
        pytest.param(LITERAL_RESERVED, None, {}, id="literal keys are not added"),
        pytest.param(COMPUTED_RESERVED, None, {}, id="computed keys are not added"),
    ],
)
def test_resolve_reserved_metadata_keys(targeting, flag_set_metadata, expected) -> None:
    extra = {} if flag_set_metadata is None else {"metadata": flag_set_metadata}
    result = evaluate(resolve_flag(targeting, **extra), {"key": "version"})
    assert result.variant == "red"
    assert result.flag_metadata["details"] == "rule"
    for key in ("flagSetId", "version"):
        if key in expected:
            assert result.flag_metadata[key] == expected[key]
        else:
            assert key not in result.flag_metadata


# a computed product that overflows to +Inf, and +Inf - +Inf is NaN; not a division by zero,
# which Python's JsonLogic raises on instead of returning Infinity or NaN
OVERFLOW = {"*": [{"var": "big"}, 10]}
NON_FINITE_METADATA = {
    "resolve": [
        "red",
        "SPLIT",
        [["share", {"if": [{"var": "nan"}, {"-": [OVERFLOW, OVERFLOW]}, OVERFLOW]}]],
    ]
}


# malformed computed arguments return null like the other custom operators,
# so the default variant is selected
@pytest.mark.parametrize(
    ("targeting", "context"),
    [
        pytest.param({"resolve": [{"var": "pick"}]}, None, id="null variant"),
        pytest.param(
            {"resolve": [{"var": "pick"}]}, {"pick": {"a": 1}}, id="object variant"
        ),
        pytest.param(
            {"resolve": [{"var": "pick"}]}, {"pick": float("nan")}, id="NaN variant"
        ),
        pytest.param(
            {"resolve": ["red", {"var": "why"}]}, {"why": 1}, id="non-string reason"
        ),
        pytest.param(
            {"resolve": ["red", None, [[{"var": "key"}, "x"]]]},
            {"key": 1},
            id="non-string metadata key",
        ),
        pytest.param(
            {"resolve": ["red", None, [["details", {"var": "obj"}]]]},
            {"obj": {"a": 1}},
            id="non-primitive metadata value",
        ),
        pytest.param(
            {"resolve": ["red", None, [["details", {"var": "missing"}]]]},
            None,
            id="null metadata value",
        ),
        pytest.param(
            {"resolve": ["red", None, {"var": "meta"}]},
            {"meta": "nope"},
            id="metadata not a list",
        ),
        pytest.param(
            {"resolve": ["red", None, [{"var": "pair"}]]},
            {"pair": ["details"]},
            id="metadata pair of one",
        ),
        pytest.param(
            {"if": [True, {"resolve": [{"var": "pick"}]}, "blue"]},
            None,
            id="inside an if result",
        ),
        pytest.param(
            {"fractional": ["key", [{"resolve": [{"var": "pick"}]}, 1], ["blue", 0]]},
            None,
            id="inside a fractional bucket",
        ),
        pytest.param(NON_FINITE_METADATA, {"big": 1e308}, id="+Inf metadata"),
        pytest.param(
            NON_FINITE_METADATA, {"big": 1e308, "nan": True}, id="NaN metadata"
        ),
    ],
)
def test_resolve_malformed_computed_arguments(targeting, context) -> None:
    result = evaluate(resolve_flag(targeting), context)
    assert result.value == "#FFFF00"
    assert result.variant == "yellow"
    assert result.reason == Reason.DEFAULT
    assert "share" not in result.flag_metadata
    assert "details" not in result.flag_metadata
    json.dumps(result.flag_metadata, allow_nan=False)


# variant keys are never empty, so an empty variant is missing too
@pytest.mark.parametrize(
    ("targeting", "context"),
    [
        pytest.param({"resolve": ["missing"]}, None, id="missing variant"),
        pytest.param({"resolve": ["", "ALLOWLIST"]}, None, id="empty variant"),
        pytest.param(
            {"resolve": [{"var": "pick"}, "ALLOWLIST"]},
            {"pick": ""},
            id="computed empty variant",
        ),
    ],
)
def test_resolve_missing_variant_fails_like_a_plain_string(targeting, context) -> None:
    with pytest.raises(GeneralError):
        evaluate(resolve_flag(targeting), context)


def test_resolve_reason_does_not_skip_type_check() -> None:
    core = FlagdCore()
    core.set_flags(resolve_flag({"resolve": ["red", "ALLOWLIST"]}))
    with pytest.raises(TypeMismatchError):
        core.resolve_boolean_value("color", False)


# context data shaped like an operator result must not be treated as one
def test_context_cannot_forge_a_resolve_result() -> None:
    context = {
        "pick": {
            "variant": "red",
            "reason": "INJECTED",
            "metadata": {"flagSetId": "spoofed"},
        }
    }
    with pytest.raises(GeneralError):
        evaluate(resolve_flag({"var": "pick"}), context)


INJECTED = {"pick": {"resolve": ["red", "INJECTED", [["flagSetId", "spoofed"]]]}}


# JsonLogic returns a single-key context map like {"resolve": [...]} from a branch as a value
# and never applies it, so the context can't call resolve; the map is just an invalid variant
@pytest.mark.parametrize(
    "targeting",
    [
        pytest.param({"if": [True, {"var": "pick"}, "blue"]}, id="nested if"),
        pytest.param({"if": [False, "blue", {"var": "pick"}]}, id="nested if else"),
        pytest.param({"?:": [True, {"var": "pick"}, "blue"]}, id="ternary"),
        pytest.param(
            {"fractional": ["key", [{"var": "pick"}, 1]]}, id="fractional bucket"
        ),
    ],
)
def test_context_cannot_invoke_resolve(targeting) -> None:
    with pytest.raises(GeneralError):
        evaluate(resolve_flag(targeting), INJECTED)


# as a resolve variant the map is malformed, so the default variant is selected
def test_context_cannot_invoke_resolve_inside_resolve() -> None:
    result = evaluate(
        resolve_flag({"resolve": [{"if": [True, {"var": "pick"}, "blue"]}]}), INJECTED
    )
    assert result.variant == "yellow"
    assert result.reason == Reason.DEFAULT
    assert "flagSetId" not in result.flag_metadata


class TestResolveOperator:
    def test_all_arguments(self) -> None:
        assert resolve({}, "red", "ALLOWLIST", [["details", "x"], ["n", 2]]) == (
            ResolveResult("red", "ALLOWLIST", {"details": "x", "n": 2})
        )

    def test_variant_only(self) -> None:
        assert resolve({}, "red") == ResolveResult("red")

    @pytest.mark.parametrize(
        "args",
        [
            pytest.param((), id="no arguments"),
            pytest.param(("red", None, [], "extra"), id="too many arguments"),
            pytest.param(("red", None, "nope"), id="metadata not a list"),
            pytest.param(("red", None, [["n", float("inf")]]), id="infinite metadata"),
            pytest.param(("red", None, [["n", float("nan")]]), id="NaN metadata"),
            pytest.param((float("inf"),), id="infinite variant"),
        ],
    )
    def test_malformed_arguments_return_none(self, args) -> None:
        assert resolve({}, *args) is None
