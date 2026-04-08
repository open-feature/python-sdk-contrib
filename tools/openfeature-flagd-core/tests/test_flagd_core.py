import json

import pytest

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError, TypeMismatchError
from openfeature.flag_evaluation import Reason

from openfeature.contrib.tools.flagd.core import FlagdCore

TEST_FLAGS = json.dumps(
    {
        "flags": {
            "bool-flag": {
                "state": "ENABLED",
                "variants": {"on": True, "off": False},
                "defaultVariant": "on",
            },
            "string-flag": {
                "state": "ENABLED",
                "variants": {"greeting": "hi", "parting": "bye"},
                "defaultVariant": "greeting",
            },
            "int-flag": {
                "state": "ENABLED",
                "variants": {"one": 1, "ten": 10},
                "defaultVariant": "ten",
            },
            "float-flag": {
                "state": "ENABLED",
                "variants": {"tenth": 0.1, "half": 0.5},
                "defaultVariant": "half",
            },
            "object-flag": {
                "state": "ENABLED",
                "variants": {"empty": {}, "full": {"key": "value"}},
                "defaultVariant": "full",
            },
            "disabled-flag": {
                "state": "DISABLED",
                "variants": {"on": True, "off": False},
                "defaultVariant": "on",
            },
            "metadata-flag": {
                "state": "ENABLED",
                "variants": {"on": True, "off": False},
                "defaultVariant": "on",
                "metadata": {"version": "1.0"},
            },
            "wrong-flag": {
                "state": "ENABLED",
                "variants": {"one": "uno", "two": "dos"},
                "defaultVariant": "one",
            },
            "null-default-flag": {
                "state": "ENABLED",
                "variants": {"on": True, "off": False},
                "defaultVariant": None,
            },
            "targeted-flag": {
                "state": "ENABLED",
                "variants": {"hi": "hi", "bye": "bye"},
                "defaultVariant": "bye",
                "targeting": {
                    "if": [
                        {"==": [{"var": "color"}, "red"]},
                        "hi",
                        "bye",
                    ]
                },
            },
        },
        "metadata": {"scope": "test"},
    }
)


@pytest.fixture()
def core() -> FlagdCore:
    c = FlagdCore()
    c.set_flags(TEST_FLAGS)
    return c


# ---- Basic resolution for all types ----


class TestBooleanResolution:
    def test_resolve_boolean(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("bool-flag", False)
        assert result.value is True
        assert result.variant == "on"
        assert result.reason == Reason.STATIC

    def test_resolve_boolean_default_value_not_used(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("bool-flag", False)
        assert result.value is True


class TestStringResolution:
    def test_resolve_string(self, core: FlagdCore) -> None:
        result = core.resolve_string_value("string-flag", "default")
        assert result.value == "hi"
        assert result.variant == "greeting"
        assert result.reason == Reason.STATIC


class TestIntegerResolution:
    def test_resolve_integer(self, core: FlagdCore) -> None:
        result = core.resolve_integer_value("int-flag", 0)
        assert result.value == 10
        assert result.variant == "ten"
        assert result.reason == Reason.STATIC


class TestFloatResolution:
    def test_resolve_float(self, core: FlagdCore) -> None:
        result = core.resolve_float_value("float-flag", 0.0)
        assert result.value == 0.5
        assert result.variant == "half"
        assert result.reason == Reason.STATIC

    def test_resolve_float_converts_int(self, core: FlagdCore) -> None:
        """Integer values should be converted to float for float resolution."""
        c = FlagdCore()
        c.set_flags(
            json.dumps(
                {
                    "flags": {
                        "int-as-float": {
                            "state": "ENABLED",
                            "variants": {"val": 42},
                            "defaultVariant": "val",
                        }
                    }
                }
            )
        )
        result = c.resolve_float_value("int-as-float", 0.0)
        assert result.value == 42.0
        assert isinstance(result.value, float)


class TestObjectResolution:
    def test_resolve_object(self, core: FlagdCore) -> None:
        result = core.resolve_object_value("object-flag", {})
        assert result.value == {"key": "value"}
        assert result.variant == "full"
        assert result.reason == Reason.STATIC


# ---- set_flags and set_flags_and_get_changed_keys ----


class TestSetFlags:
    def test_set_flags_replaces_store(self) -> None:
        core = FlagdCore()
        core.set_flags(TEST_FLAGS)
        result = core.resolve_boolean_value("bool-flag", False)
        assert result.value is True

        # Replace with different flags
        core.set_flags(
            json.dumps(
                {
                    "flags": {
                        "new-flag": {
                            "state": "ENABLED",
                            "variants": {"a": "alpha"},
                            "defaultVariant": "a",
                        }
                    }
                }
            )
        )
        result = core.resolve_string_value("new-flag", "x")
        assert result.value == "alpha"

        with pytest.raises(FlagNotFoundError):
            core.resolve_boolean_value("bool-flag", False)

    def test_set_flags_and_get_changed_keys_returns_added(self) -> None:
        core = FlagdCore()
        changed = core.set_flags_and_get_changed_keys(TEST_FLAGS)
        # All flags are new so they should all be in the changed list
        assert "bool-flag" in changed
        assert "string-flag" in changed

    def test_set_flags_and_get_changed_keys_returns_removed(self) -> None:
        core = FlagdCore()
        core.set_flags(TEST_FLAGS)
        changed = core.set_flags_and_get_changed_keys(
            json.dumps(
                {
                    "flags": {
                        "bool-flag": {
                            "state": "ENABLED",
                            "variants": {"on": True, "off": False},
                            "defaultVariant": "on",
                        }
                    }
                }
            )
        )
        # string-flag etc. were removed, so they appear as changed
        assert "string-flag" in changed

    def test_set_flags_and_get_changed_keys_detects_modifications(self) -> None:
        core = FlagdCore()
        core.set_flags(TEST_FLAGS)
        changed = core.set_flags_and_get_changed_keys(
            json.dumps(
                {
                    "flags": {
                        "bool-flag": {
                            "state": "ENABLED",
                            "variants": {"on": True, "off": False},
                            "defaultVariant": "off",  # changed default
                        },
                        "string-flag": {
                            "state": "ENABLED",
                            "variants": {"greeting": "hi", "parting": "bye"},
                            "defaultVariant": "greeting",
                        },
                    }
                }
            )
        )
        assert "bool-flag" in changed
        # string-flag is unchanged
        assert "string-flag" not in changed


# ---- DISABLED flag handling ----


class TestDisabledFlag:
    def test_disabled_returns_default_value(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("disabled-flag", False)
        assert result.value is False
        assert result.reason == Reason.DISABLED

    def test_disabled_returns_caller_default(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("disabled-flag", True)
        assert result.value is True
        assert result.reason == Reason.DISABLED


# ---- FLAG_NOT_FOUND for missing flags ----


class TestFlagNotFound:
    def test_missing_flag_raises(self, core: FlagdCore) -> None:
        with pytest.raises(FlagNotFoundError):
            core.resolve_string_value("nonexistent-flag", "default")


# ---- Targeting rule evaluation ----


class TestTargeting:
    def test_targeting_match(self, core: FlagdCore) -> None:
        ctx = EvaluationContext(attributes={"color": "red"})
        result = core.resolve_string_value("targeted-flag", "fallback", ctx)
        assert result.value == "hi"
        assert result.variant == "hi"
        assert result.reason == Reason.TARGETING_MATCH

    def test_targeting_no_match_returns_other_branch(self, core: FlagdCore) -> None:
        ctx = EvaluationContext(attributes={"color": "blue"})
        result = core.resolve_string_value("targeted-flag", "fallback", ctx)
        assert result.value == "bye"
        assert result.variant == "bye"
        assert result.reason == Reason.TARGETING_MATCH

    def test_targeting_returns_none_falls_to_default(self, core: FlagdCore) -> None:
        """When targeting returns None, fall back to flag's default variant."""
        c = FlagdCore()
        c.set_flags(
            json.dumps(
                {
                    "flags": {
                        "null-targeting": {
                            "state": "ENABLED",
                            "variants": {"a": "alpha", "b": "bravo"},
                            "defaultVariant": "a",
                            "targeting": {
                                "if": [
                                    {"==": [{"var": "x"}, "match"]},
                                    "b",
                                    None,
                                ]
                            },
                        }
                    }
                }
            )
        )
        ctx = EvaluationContext(attributes={"x": "no-match"})
        result = c.resolve_string_value("null-targeting", "fallback", ctx)
        assert result.value == "alpha"
        assert result.variant == "a"
        assert result.reason == Reason.DEFAULT


# ---- Metadata merging ----


class TestMetadata:
    def test_flag_set_metadata(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("bool-flag", False)
        assert result.flag_metadata is not None
        assert result.flag_metadata["scope"] == "test"

    def test_flag_level_metadata_merged(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("metadata-flag", False)
        assert result.flag_metadata is not None
        # flag-level metadata
        assert result.flag_metadata["version"] == "1.0"
        # flag-set-level metadata
        assert result.flag_metadata["scope"] == "test"

    def test_flag_metadata_overrides_flagset(self) -> None:
        """Flag-level metadata should override flag-set-level metadata."""
        c = FlagdCore()
        c.set_flags(
            json.dumps(
                {
                    "flags": {
                        "f": {
                            "state": "ENABLED",
                            "variants": {"on": True},
                            "defaultVariant": "on",
                            "metadata": {"scope": "override"},
                        }
                    },
                    "metadata": {"scope": "global"},
                }
            )
        )
        result = c.resolve_boolean_value("f", False)
        assert result.flag_metadata["scope"] == "override"

    def test_get_flag_set_metadata(self, core: FlagdCore) -> None:
        meta = core.get_flag_set_metadata()
        assert meta == {"scope": "test"}


# ---- No-default-variant handling ----


class TestNoDefaultVariant:
    def test_null_default_variant_returns_caller_default(self, core: FlagdCore) -> None:
        """When defaultVariant is null, return the caller's default value."""
        result = core.resolve_boolean_value("null-default-flag", True)
        assert result.value is True
        assert result.reason == Reason.DEFAULT

    def test_null_default_variant_returns_caller_false(self, core: FlagdCore) -> None:
        result = core.resolve_boolean_value("null-default-flag", False)
        assert result.value is False
        assert result.reason == Reason.DEFAULT


# ---- Type mismatch ----


class TestTypeMismatch:
    def test_string_flag_resolved_as_integer_raises(self, core: FlagdCore) -> None:
        """Resolving a string-valued flag as integer should raise TypeMismatchError."""
        with pytest.raises(TypeMismatchError):
            core.resolve_integer_value("wrong-flag", 13)

    def test_string_flag_resolved_as_boolean_raises(self, core: FlagdCore) -> None:
        with pytest.raises(TypeMismatchError):
            core.resolve_boolean_value("string-flag", False)

    def test_bool_flag_resolved_as_string_raises(self, core: FlagdCore) -> None:
        with pytest.raises(TypeMismatchError):
            core.resolve_string_value("bool-flag", "default")


# ---- $evaluators support ----


class TestEvaluators:
    def test_evaluator_ref_expansion(self) -> None:
        c = FlagdCore()
        c.set_flags(
            json.dumps(
                {
                    "flags": {
                        "ref-flag": {
                            "state": "ENABLED",
                            "variants": {"hi": "hello", "bye": "goodbye"},
                            "defaultVariant": "bye",
                            "targeting": {
                                "if": [{"$ref": "is_admin"}, "hi", "bye"]
                            },
                        }
                    },
                    "$evaluators": {
                        "is_admin": {"==": [{"var": "role"}, "admin"]}
                    },
                }
            )
        )
        ctx = EvaluationContext(attributes={"role": "admin"})
        result = c.resolve_string_value("ref-flag", "fallback", ctx)
        assert result.value == "hello"
        assert result.reason == Reason.TARGETING_MATCH
