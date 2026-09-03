from openfeature.contrib.tools.flagd.core.targeting import targeting
from openfeature.contrib.tools.flagd.core.targeting.custom_ops import (
    ends_with,
    fractional,
    normalize_numbers,
    sem_ver,
    starts_with,
)
from openfeature.evaluation_context import EvaluationContext


class TestTargetingFunction:
    def test_simple_if_targeting(self) -> None:
        rule = {"if": [{"==": [{"var": "color"}, "blue"]}, "match", "no-match"]}
        ctx = EvaluationContext(attributes={"color": "blue"})
        result = targeting("test-flag", rule, ctx)
        assert result == "match"

    def test_targeting_no_match(self) -> None:
        rule = {"if": [{"==": [{"var": "color"}, "blue"]}, "match", "no-match"]}
        ctx = EvaluationContext(attributes={"color": "red"})
        result = targeting("test-flag", rule, ctx)
        assert result == "no-match"

    def test_targeting_with_targeting_key(self) -> None:
        rule = {
            "if": [
                {"==": [{"var": "targetingKey"}, "user-123"]},
                "hit",
                "miss",
            ]
        }
        ctx = EvaluationContext(targeting_key="user-123")
        result = targeting("test-flag", rule, ctx)
        assert result == "hit"

    def test_targeting_includes_flagd_context(self) -> None:
        """$flagd.flagKey should be set in the context."""
        rule = {
            "if": [
                {"==": [{"var": "$flagd.flagKey"}, "my-flag"]},
                "yes",
                "no",
            ]
        }
        result = targeting("my-flag", rule)
        assert result == "yes"

    def test_targeting_without_context(self) -> None:
        rule = {"if": [True, "a", "b"]}
        result = targeting("flag", rule)
        assert result == "a"


class TestStartsWith:
    def test_starts_with_true(self) -> None:
        result = starts_with({}, "hello world", "hello")
        assert result is True

    def test_starts_with_false(self) -> None:
        result = starts_with({}, "hello world", "world")
        assert result is False

    def test_starts_with_no_args(self) -> None:
        result = starts_with({})
        assert result is None

    def test_starts_with_non_string(self) -> None:
        result = starts_with({}, 123, "abc")
        assert result is None


class TestEndsWith:
    def test_ends_with_true(self) -> None:
        result = ends_with({}, "hello world", "world")
        assert result is True

    def test_ends_with_false(self) -> None:
        result = ends_with({}, "hello world", "hello")
        assert result is False

    def test_ends_with_non_string(self) -> None:
        result = ends_with({}, 123, "abc")
        assert result is None


class TestSemVer:
    def test_equal(self) -> None:
        assert sem_ver({}, "2.0.0", "=", "2.0.0") is True

    def test_not_equal(self) -> None:
        assert sem_ver({}, "2.0.0", "!=", "1.0.0") is True

    def test_less_than(self) -> None:
        assert sem_ver({}, "1.0.0", "<", "2.0.0") is True

    def test_greater_than(self) -> None:
        assert sem_ver({}, "3.0.0", ">", "2.0.0") is True

    def test_less_equal(self) -> None:
        assert sem_ver({}, "2.0.0", "<=", "2.0.0") is True

    def test_greater_equal(self) -> None:
        assert sem_ver({}, "2.0.0", ">=", "2.0.0") is True

    def test_major_match(self) -> None:
        assert sem_ver({}, "3.1.0", "^", "3.0.0") is True

    def test_major_no_match(self) -> None:
        assert sem_ver({}, "4.0.0", "^", "3.0.0") is False

    def test_minor_match(self) -> None:
        assert sem_ver({}, "3.0.1", "~", "3.0.0") is True

    def test_minor_no_match(self) -> None:
        assert sem_ver({}, "3.1.0", "~", "3.0.0") is False

    def test_v_prefix(self) -> None:
        assert sem_ver({}, "v2.0.0", "=", "2.0.0") is True

    def test_partial_major_version(self) -> None:
        assert sem_ver({}, "2", "=", "2.0.0") is True

    def test_partial_minor_version(self) -> None:
        assert sem_ver({}, "v1.2", "=", "1.2.0") is True

    def test_invalid_version(self) -> None:
        result = sem_ver({}, "not-a-version", "=", "1.0.0")
        assert result is None

    def test_invalid_operator(self) -> None:
        result = sem_ver({}, "1.0.0", "===", "1.0.0")
        assert result is None

    def test_no_args(self) -> None:
        result = sem_ver({})
        assert result is None

    def test_wrong_arg_count(self) -> None:
        result = sem_ver({}, "1.0.0", "=")
        assert result is None


class TestFractional:
    def test_fractional_with_explicit_key(self) -> None:
        """Fractional with an explicit bucket key should return a variant."""
        result = fractional(
            {},
            "test-key",
            ["a", 50],
            ["b", 50],
        )
        assert result in ("a", "b")

    def test_fractional_with_targeting_key(self) -> None:
        """Fractional shorthand uses targetingKey + flagKey as seed."""
        data = {
            "targetingKey": "user-1",
            "$flagd": {"flagKey": "my-flag"},
        }
        result = fractional(
            data,
            ["heads", 50],
            ["tails", 50],
        )
        assert result in ("heads", "tails")

    def test_fractional_no_targeting_key(self) -> None:
        """Fractional without targetingKey returns None."""
        data = {"$flagd": {"flagKey": "my-flag"}}
        result = fractional(
            data,
            ["a", 50],
            ["b", 50],
        )
        assert result is None

    def test_fractional_no_args(self) -> None:
        result = fractional({})
        assert result is None

    def test_fractional_deterministic(self) -> None:
        """Same input should always produce same output."""
        results = set()
        for _ in range(10):
            r = fractional({}, "stable-key", ["x", 50], ["y", 50])
            results.add(r)
        assert len(results) == 1

    def test_fractional_null_bucket_key(self) -> None:
        """Fractional with explicit null bucket key returns None."""
        assert fractional({}, None, ["a", 50], ["b", 50]) is None

    def test_fractional_shorthand_non_string_targeting_key(self) -> None:
        """Shorthand with non-string targetingKey (int, bool) returns None."""
        int_data = {"targetingKey": 12345, "$flagd": {"flagKey": "my-flag"}}
        assert fractional(int_data, ["a", 50], ["b", 50]) is None

        bool_data = {"targetingKey": True, "$flagd": {"flagKey": "my-flag"}}
        assert fractional(bool_data, ["a", 50], ["b", 50]) is None

    def test_fractional_non_string_types(self) -> None:
        """Fractional should support int, float, bool, and dict (with nested lists)."""
        for key in [123, 1.23, True, False, {"user": 1}, {"tags": ["tag1", "tag2"]}]:
            result = fractional({}, key, ["a", 50], ["b", 50])
            assert result in ("a", "b")

    def test_fractional_top_level_array_not_explicit_key(self) -> None:
        """Top-level array is reserved for variant buckets (shorthand syntax) per ADR."""
        # When no targetingKey in context, shorthand fails and returns None
        result = fractional({}, ["tag1", "tag2"], ["a", 50], ["b", 50])
        assert result is None

    def test_fractional_float_int_equivalence(self) -> None:
        """1.0 and 1 must produce the exact same bucket assignment."""
        res_float = fractional({}, 1.0, ["a", 50], ["b", 50])
        res_int = fractional({}, 1, ["a", 50], ["b", 50])
        assert res_float == res_int

    def test_fractional_zero_values_equivalence(self) -> None:
        """0.0, -0.0, and 0 must produce the exact same bucket assignment."""
        res_pos_zero = fractional({}, 0.0, ["a", 50], ["b", 50])
        res_neg_zero = fractional({}, -0.0, ["a", 50], ["b", 50])
        res_int_zero = fractional({}, 0, ["a", 50], ["b", 50])
        assert res_pos_zero == res_neg_zero == res_int_zero

    def test_fractional_dict_key_ordering(self) -> None:
        """Dicts with different key insertion order must evaluate identically."""
        res_ab = fractional({}, {"a": 1, "b": 2}, ["a", 50], ["b", 50])
        res_ba = fractional({}, {"b": 2, "a": 1}, ["a", 50], ["b", 50])
        assert res_ab == res_ba

    def test_fractional_zero_total_weight(self) -> None:
        """All-zero weights should return None."""
        assert fractional({}, "user", ["a", 0], ["b", 0]) is None

    def test_fractional_negative_weight_clamping(self) -> None:
        """Negative weights should be clamped to 0."""
        assert fractional({}, "user", ["a", -50], ["b", 100]) == "b"


class TestNormalizeNumbers:
    def test_float_to_int(self) -> None:
        assert normalize_numbers(1.0) == 1
        assert isinstance(normalize_numbers(1.0), int)
        assert normalize_numbers(-2.0) == -2
        assert isinstance(normalize_numbers(-2.0), int)

    def test_float_with_fractional_part_unchanged(self) -> None:
        assert normalize_numbers(1.25) == 1.25
        assert isinstance(normalize_numbers(1.25), float)

    def test_nested_dict_and_list(self) -> None:
        data = {"a": 2.0, "b": [3.0, {"c": 4.5}]}
        norm = normalize_numbers(data)
        assert norm == {"a": 2, "b": [3, {"c": 4.5}]}
        assert isinstance(norm["a"], int)
        assert isinstance(norm["b"][0], int)
        assert isinstance(norm["b"][1]["c"], float)

    def test_out_of_range_float_stays_float(self) -> None:
        huge = 1e100
        norm = normalize_numbers(huge)
        assert norm == huge
        assert isinstance(norm, float)
