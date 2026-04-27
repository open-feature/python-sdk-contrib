from openfeature.contrib.tools.flagd.core.targeting import targeting
from openfeature.contrib.tools.flagd.core.targeting.custom_ops import (
    ends_with,
    fractional,
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
