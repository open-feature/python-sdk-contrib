import itertools
import time
import typing
import unittest
from dataclasses import dataclass
from enum import Enum
from math import floor

import pytest
from json_logic import builtins, jsonLogic  # type: ignore[import-untyped]

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
    rule: typing.List[str]
    result: typing.Optional[bool]


semver_operations: typing.List[SemVerTest] = [
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
        assert logic == "blue"

    def test_should_evaluate_valid_rule_with_targeting_key(self):
        rule = {
            "fractional": [
                ["red", 50],
                ["blue", 50],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="bucketKeyB"))
        assert logic == "blue"

    def test_should_evaluate_valid_rule_with_targeting_key_although_one_does_not_have_a_fraction(
        self,
    ):
        rule = {
            "fractional": [["red", 1], ["blue"]],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="bucketKeyB"))
        assert logic == "blue"

    def test_should_return_null_if_targeting_key_is_missing(self):
        rule = {
            "fractional": [
                ["red", 1],
                ["blue", 1],
            ],
        }

        logic = jsonLogic(rule, {}, OPERATORS)
        assert logic is None

    def test_bucket_sum_with_sum_bigger_than_100(self):
        rule = {
            "fractional": [
                ["red", 55],
                ["blue", 55],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == "blue"

    def test_bucket_sum_with_sum_lower_than_100(self):
        rule = {
            "fractional": [
                ["red", 45],
                ["blue", 45],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic == "blue"

    def test_buckets_properties_to_have_variant_and_fraction(self):
        rule = {
            "fractional": [
                ["red", 50],
                [100, 50],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None

    def test_buckets_properties_to_have_variant_and_fraction2(self):
        rule = {
            "fractional": [
                ["red", 45, 1256],
                ["blue", 4, 455],
            ],
        }

        logic = targeting("flagA", rule, EvaluationContext(targeting_key="key"))
        assert logic is None
