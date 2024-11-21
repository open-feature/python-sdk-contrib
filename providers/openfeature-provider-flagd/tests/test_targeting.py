import time
import unittest
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


@pytest.mark.skip(
    "semvers are not working as expected, 'v' prefix is not valid within current implementation"
)
class SemVerOperator(unittest.TestCase):
    def test_should_support_equal_operator(self):
        rule = {"sem_ver": ["v1.2.3", "=", "1.2.3"]}

        assert targeting(flag_key, rule)

    def test_should_support_neq_operator(self):
        rule = {"sem_ver": ["v1.2.3", "!=", "1.2.4"]}

        assert targeting(flag_key, rule)

    def test_should_support_lt_operator(self):
        rule = {"sem_ver": ["v1.2.3", "<", "1.2.4"]}

        assert targeting(flag_key, rule)

    def test_should_support_lte_operator(self):
        rule = {"sem_ver": ["v1.2.3", "<=", "1.2.3"]}

        assert targeting(flag_key, rule)

    def test_should_support_gte_operator(self):
        rule = {"sem_ver": ["v1.2.3", ">=", "1.2.3"]}

        assert targeting(flag_key, rule)

    def test_should_support_gt_operator(self):
        rule = {"sem_ver": ["v1.2.4", ">", "1.2.3"]}

        assert targeting(flag_key, rule)

    def test_should_support_major_comparison_operator(self):
        rule = {"sem_ver": ["v1.2.3", "^", "v1.0.0"]}

        assert targeting(flag_key, rule)

    def test_should_support_minor_comparison_operator(self):
        rule = {"sem_ver": ["v5.0.3", "~", "v5.0.8"]}

        assert targeting(flag_key, rule)

    def test_should_handle_unknown_operator(self):
        rule = {"sem_ver": ["v1.0.0", "-", "v1.0.0"]}

        assert targeting(flag_key, rule)

    def test_should_handle_invalid_targetings(self):
        rule = {"sem_ver": ["myVersion_1", "=", "myVersion_1"]}

        assert not targeting(flag_key, rule)

    def test_should_validate_targetings(self):
        rule = {"sem_ver": ["myVersion_2", "+", "myVersion_1", "myVersion_1"]}

        assert targeting(flag_key, rule)


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
