import json
from unittest.mock import Mock, create_autospec

import pytest

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.in_process import InProcessResolver
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError, GeneralError


def _targeting_rule():
    return {
        "if": [
            {"==": [{"var": "targetingKey"}, "target_variant"]},
            "target_variant",
            None,
        ]
    }


def _flag_config(variants, targeting=None, state="ENABLED", default_variant="default_variant"):
    return {
        "flags": {
            "flag": {
                "state": state,
                "variants": variants,
                "defaultVariant": default_variant,
                **({"targeting": targeting} if targeting else {}),
            }
        }
    }


def context(targeting_key):
    return EvaluationContext(targeting_key=targeting_key)


@pytest.fixture
def config():
    return create_autospec(Config)


@pytest.fixture
def resolver(config):
    config.offline_flag_source_path = "flag.json"
    config.deadline_ms = 100
    return InProcessResolver(
        config=config,
        emit_provider_ready=Mock(),
        emit_provider_error=Mock(),
        emit_provider_stale=Mock(),
        emit_provider_configuration_changed=Mock(),
    )


def test_resolve_boolean_details_flag_not_found(resolver):
    with pytest.raises(FlagNotFoundError):
        resolver.resolve_boolean_details("nonexistent_flag", False)


def test_resolve_boolean_details_disabled_flag(resolver):
    flags = _flag_config(
        variants={"default_variant": False, "target_variant": True},
        state="DISABLED",
    )
    resolver.evaluator.set_flags(json.dumps(flags))

    result = resolver.resolve_boolean_details("flag", False)

    assert result.reason == "DISABLED"
    assert result.variant is None
    assert not result.value


def test_resolve_boolean_details_invalid_variant(resolver):
    flags = _flag_config(
        variants={"default_variant": False, "target_variant": True},
        targeting={"var": ["targetingKey", "invalid_variant"]},
    )
    resolver.evaluator.set_flags(json.dumps(flags))

    with pytest.raises(GeneralError):
        resolver.resolve_boolean_details("flag", False)


@pytest.mark.parametrize(
    "input_config, resolve_config, expected",
    [
        (
            {
                "variants": {"default_variant": False, "target_variant": True},
                "targeting": None,
            },
            {
                "context": None,
                "method": "resolve_boolean_details",
                "default_value": False,
            },
            {"reason": "STATIC", "variant": "default_variant", "value": False},
        ),
        (
            {
                "variants": {"default_variant": False, "target_variant": True},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("no_target_variant"),
                "method": "resolve_boolean_details",
                "default_value": False,
            },
            {"reason": "DEFAULT", "variant": "default_variant", "value": False},
        ),
        (
            {
                "variants": {"default_variant": False, "target_variant": True},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_boolean_details",
                "default_value": False,
            },
            {"reason": "TARGETING_MATCH", "variant": "target_variant", "value": True},
        ),
        (
            {
                "variants": {"default_variant": "default", "target_variant": "target"},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_string_details",
                "default_value": "placeholder",
            },
            {
                "reason": "TARGETING_MATCH",
                "variant": "target_variant",
                "value": "target",
            },
        ),
        (
            {
                "variants": {"default_variant": 1.0, "target_variant": 2.0},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_float_details",
                "default_value": 0.0,
            },
            {"reason": "TARGETING_MATCH", "variant": "target_variant", "value": 2.0},
        ),
        (
            {
                "variants": {"default_variant": True, "target_variant": False},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_boolean_details",
                "default_value": True,
            },
            {"reason": "TARGETING_MATCH", "variant": "target_variant", "value": False},
        ),
        (
            {
                "variants": {"default_variant": 10, "target_variant": 0},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_integer_details",
                "default_value": 1,
            },
            {"reason": "TARGETING_MATCH", "variant": "target_variant", "value": 0},
        ),
        (
            {
                "variants": {"default_variant": {}, "target_variant": {}},
                "targeting": _targeting_rule(),
            },
            {
                "context": context("target_variant"),
                "method": "resolve_object_details",
                "default_value": {},
            },
            {"reason": "TARGETING_MATCH", "variant": "target_variant", "value": {}},
        ),
    ],
    ids=[
        "static_flag",
        "boolean_default_fallback",
        "boolean_targeting_match",
        "string_targeting_match",
        "float_targeting_match",
        "boolean_falsy_target",
        "integer_falsy_target",
        "object_falsy_target",
    ],
)
def test_resolver_details(
    resolver,
    input_config,
    resolve_config,
    expected,
):
    flags = _flag_config(
        variants=input_config["variants"],
        targeting=input_config.get("targeting"),
    )
    resolver.evaluator.set_flags(json.dumps(flags))

    result = getattr(resolver, resolve_config["method"])(
        "flag", resolve_config["default_value"], resolve_config["context"]
    )

    assert result.reason == expected["reason"]
    assert result.variant == expected["variant"]
    assert result.value == expected["value"]
