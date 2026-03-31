import itertools
import time
import unittest
from dataclasses import dataclass
from enum import Enum
from math import floor

import pytest
from json_logic import builtins, jsonLogic

from openfeature.contrib.provider.flagd.resolvers.process.custom_ops import (
    ends_with,
    fractional,
    sem_ver,
    starts_with,
)
from openfeature.contrib.provider.flagd.resolvers.process.targeting import targeting
from openfeature.evaluation_context import EvaluationContext

OPERATORS = {
    **builtins.BUILTINS,
    "fractional": fractional,
    "starts_with": starts_with,
    "ends_with": ends_with,
    "sem_ver": sem_ver,
}

flag_key = "flagKey"


class BasicTests(unittest.TestCase):
    def test_should_inject_flag_key_as_a_property(self):
        rule = {"===": [{"var": "$flagd.flagKey"}, flag_key]}

        result = targeting(flag_key, rule)

        assert result

    def test_should_inject_current_timestamp_as_a_property(self):
        ts = floor(time.time() / 1000)

        rule = {">=": [{"var": "$flagd.timestamp"}, ts]}

        assert targeting(flag_key, rule)

    def test_should_override_injected_properties_if_already_present_in_context(self):
        rule = {"===": [{"var": "$flagd.flagKey"}, flag_key]}

        ctx = {
            "$flagd": {
                "flagKey": "someOtherFlag",
            },
        }

        assert targeting(flag_key, rule, EvaluationContext(attributes=ctx))


class StringComparisonOperator(unittest.TestCase):
    def test_should_evaluate_starts_with_calls(self):
        rule = {"starts_with": [{"var": "email"}, "admin"]}
        context = {"email": "admin@abc.com"}

        assert targeting(flag_key, rule, EvaluationContext(attributes=context))

    def test_should_evaluate_ends_with_calls(self):
        rule = {"ends_with": [{"var": "email"}, "abc.com"]}
        context = {"email": "admin@abc.com"}

        assert targeting(flag_key, rule, EvaluationContext(attributes=context))

    def test_missing_targeting(self):
        rule = {"starts_with": [{"var": "email"}]}
        context = {"email": "admin@abc.com"}

        assert not targeting(flag_key, rule, EvaluationContext(attributes=context))

    def test_non_string_variable(self):
        rule = {"ends_with": [{"var": "number"}, "abc.com"]}
        context = {"number": 11111}

        assert not targeting(flag_key, rule, EvaluationContext(attributes=context))

    def test_non_string_comparator(self):
        rule = {"ends_with": [{"var": "email"}, 111111]}
        context = {"email": "admin@abc.com"}

        assert not targeting(flag_key, rule, EvaluationContext(attributes=context))


class VersionPrefixed(Enum):
    NONE = "None"
    FIRST = "First"
    SECOND = "Second"
    BOTH = "Both"


@dataclass
class SemVerTest:
    title: str
    rule: list[str]
    result: bool | None


semver_operations: list[SemVerTest] = [
    # Successful and working rules
    SemVerTest("equals", ["1.2.3", "=", "1.2.3"], True),
    SemVerTest("not equals", ["1.2.3", "!=", "1.2.4"], True),
    SemVerTest("lesser", ["1.2.3", "<", "1.2.4"], True),
    SemVerTest("lesser equals", ["1.2.3", "<=", "1.2.3"], True),
    SemVerTest("greater", ["1.2.4", ">", "1.2.3"], True),
    SemVerTest("greater equals", ["1.2.3", ">=", "1.2.3"], True),
    SemVerTest("match major", ["1.2.3", "^", "1.0.0"], True),
    SemVerTest("match minor", ["5.0.3", "~", "5.0.8"], True),
    # Wrong rules
    SemVerTest("wrong operator", ["1.0.0", "-", "1.0.0"], None),
    SemVerTest("wrong versions", ["myVersion_1", "=", "myVersion_1"], None),
    SemVerTest(
        "too many arguments", ["myVersion_2", "+", "myVersion_1", "myVersion_1"], None
    ),
    SemVerTest("too many arguments", ["1.2.3", "=", "1.2.3", "myVersion_1"], None),
]


def semver_test_naming(vals):
    if isinstance(vals, SemVerTest):
        return vals.title
    elif isinstance(vals, VersionPrefixed):
        return f"prefixing '{vals.value}'"
    elif isinstance(vals, str):
        return f"with '{vals}'"


@pytest.mark.parametrize(
    ("semver_test", "prefix_state", "prefix"),
    itertools.product(semver_operations, VersionPrefixed, ["V", "v"]),
    ids=semver_test_naming,
)
def test_sem_ver_operator(semver_test: SemVerTest, prefix_state, prefix):
    """Testing SemVer operator `semver_test.title` for `semver_test.rule` prefixing `prefix_state.value` version(s) with `prefix`"""
    version1 = semver_test.rule[0]
    operator = semver_test.rule[1]
    version2 = semver_test.rule[2]

    if prefix_state is VersionPrefixed.FIRST or prefix_state is VersionPrefixed.BOTH:
        version1 = prefix + version1

    if prefix_state is VersionPrefixed.SECOND or prefix_state is VersionPrefixed.BOTH:
        version2 = prefix + version2

    semver_rule = [version1, operator, version2]
    semver_rule.extend(semver_test.rule[3:])

    gen_rule = {"sem_ver": semver_rule}

    assert targeting(flag_key, gen_rule) is semver_test.result


class FractionalOperator(unittest.TestCase):
    def test_should_evaluate_valid_rule(self):
        rule = {
            "fractional": [
                {"cat": [{"var": "$flagd.flagKey"}, {"var": "key"}]},
                ["red", 50],
                ["blue", 50],
            ],
        }

        logic = targeting(
            "flagA", rule, EvaluationContext(attributes={"key": "bucketKeyA"})
        )
        assert logic == "red"

    def test_should_evaluate_valid_rule2(self):
        rule = {
            "fractional": [
                {"cat": [{"var": "$flagd.flagKey"}, {"var": "key"}]},
                ["red", 50],
                ["blue", 50],
            ],
        }

        logic = targeting(
            "flagA", rule, EvaluationContext(attributes={"key": "bucketKeyB"})
        )
        assert logic == "red"

    def test_should_evaluate_valid_rule_with_targeting_key(self):
        rule = {
            "fractional": [
                ["red", 50],
                ["blue", 50],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="bucketKeyB"))
        assert logic == "red"

    def test_should_evaluate_valid_rule_with_targeting_key_although_one_does_not_have_a_fraction(
        self,
    ):
        rule = {
            "fractional": [["red", 1], ["blue"]],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="bucketKeyB"))
        assert logic == "red"

    def test_should_return_null_if_targeting_key_is_missing(self):
        rule = {
            "fractional": [
                ["red", 1],
                ["blue", 1],
            ],
        }

        logic = jsonLogic(rule, {}, OPERATORS)
        assert logic is None

    def test_no_args_returns_none(self):
        logic = fractional({})
        assert logic is None

    def test_omitted_weight_defaults_to_1(self):
        rule = {
            "fractional": [["red", 1], ["blue"]],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="bucketKeyB"))
        assert logic == "red"

    def test_weight_zero_bucket_never_wins(self):
        rule = {
            "fractional": [
                ["never", 0],
                ["always", 1],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="any"))
        assert logic == "always"

    def test_negative_weight_clamped_to_zero(self):
        rule = {
            "fractional": [
                ["on", -1000],
                ["off", 1],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="any"))
        assert logic == "off"

    def test_weight_as_fractional_float_is_invalid(self):
        rule = {
            "fractional": [
                ["red", 50.0],
                ["blue", 50],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_weight_as_bool_is_invalid(self):
        rule = {
            "fractional": [
                ["red", True],
                ["blue", 50],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_weight_as_string_is_invalid(self):
        rule = {
            "fractional": [
                ["red", "50"],
                ["blue", 50],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_dynamic_weight_from_var_expression(self):
        # seed="flagAkey" → bucket=55; rolloutPercent=70 → new-feature=[0,70), control=[70,100)
        rule = {
            "fractional": [
                ["new-feature", {"var": "rolloutPercent"}],
                ["control", {"-": [100, {"var": "rolloutPercent"}]}],
            ],
        }
        logic = targeting(
            "flagA",
            rule,
            EvaluationContext(targeting_key="key", attributes={"rolloutPercent": 70}),
        )
        assert logic == "new-feature"

    def test_total_weight_exceeds_max_int32_returns_none(self):
        logic = targeting(
            "flagA",
            {"fractional": [["red", 2_147_483_647], ["blue", 1]]},
            EvaluationContext(targeting_key="key"),
        )
        assert logic is None

    def test_variant_as_string(self):
        rule = {"fractional": [["red", 1]]}
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == "red"

    def test_variant_as_int(self):
        rule = {"fractional": [[42, 1]]}
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == 42

    def test_variant_as_float(self):
        rule = {"fractional": [[3.14, 1]]}
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == 3.14

    def test_variant_as_bool_true(self):
        rule = {"fractional": [[True, 1]]}
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is True

    def test_variant_as_none(self):
        rule = {"fractional": [[None, 1]]}
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_mixed_variant_types_all_participate(self):
        # seed="flagAkey", 4 buckets weight 1 each → bucket=2 → third bucket → variant=1 (int)
        rule = {
            "fractional": [
                ["clubs", 1],
                [True, 1],
                [1, 1],
                [None, 1],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == 1

    def test_nested_if_as_variant_name(self):
        rule = {
            "fractional": [
                {"var": "targetingKey"},
                [
                    {
                        "if": [
                            {"==": [{"var": "tier"}, "premium"]},
                            "premium",
                            "standard",
                        ]
                    },
                    50,
                ],
                ["standard", 50],
            ],
        }
        assert (
            targeting(
                "fractional-nested-if-flag",
                rule,
                EvaluationContext(
                    targeting_key="jon@company.com", attributes={"tier": "premium"}
                ),
            )
            == "premium"
        )
        assert (
            targeting(
                "fractional-nested-if-flag",
                rule,
                EvaluationContext(
                    targeting_key="jon@company.com", attributes={"tier": "basic"}
                ),
            )
            == "standard"
        )

    def test_nested_var_as_variant_name_resolved(self):
        rule = {
            "fractional": [
                {"var": "targetingKey"},
                [{"var": "color"}, 50],
                ["blue", 50],
            ],
        }
        assert (
            targeting(
                "fractional-nested-var-flag",
                rule,
                EvaluationContext(
                    targeting_key="jon@company.com", attributes={"color": "red"}
                ),
            )
            == "red"
        )

    def test_nested_var_as_variant_name_absent_key_resolves_to_none(self):
        rule = {
            "fractional": [
                {"var": "targetingKey"},
                [{"var": "color"}, 50],
                ["blue", 50],
            ],
        }
        logic = targeting(
            "fractional-nested-var-flag",
            rule,
            EvaluationContext(targeting_key="jon@company.com"),
        )
        assert logic is None

    def test_nested_fractional_as_variant_name(self):
        # json_logic evaluates the inner {"fractional":[...]} before the outer one sees it.
        # Inner: seed="flagAkey", bucket=55 → hearts=[50,75) → "hearts".
        # Outer: seed="flagAkey", bucket=1, buckets are ["clubs",1]=[0,1) and [inner,1]=[1,2) → inner & "hearts".
        inner = {
            "fractional": [
                ["clubs", 25],
                ["diamonds", 25],
                ["hearts", 25],
                ["spades", 25],
            ]
        }
        rule = {
            "fractional": [
                ["clubs", 1],
                [inner, 1],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == "hearts"

    def test_nested_if_as_weight(self):
        rule = {
            "fractional": [
                {"var": "targetingKey"},
                ["red", {"if": [{"==": [{"var": "tier"}, "premium"]}, 100, 0]}],
                ["blue", 10],
            ],
        }
        assert (
            targeting(
                "fractional-nested-weight-flag",
                rule,
                EvaluationContext(
                    targeting_key="jon@company.com", attributes={"tier": "premium"}
                ),
            )
            == "red"
        )
        assert (
            targeting(
                "fractional-nested-weight-flag",
                rule,
                EvaluationContext(
                    targeting_key="jon@company.com", attributes={"tier": "basic"}
                ),
            )
            == "blue"
        )

    def test_bucket_too_many_elements_returns_none(self):
        rule = {
            "fractional": [
                ["red", 45, 1256],
                ["blue", 4, 455],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_bucket_empty_list_returns_none(self):
        rule = {
            "fractional": [
                [],
                ["blue", 1],
            ],
        }
        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None
