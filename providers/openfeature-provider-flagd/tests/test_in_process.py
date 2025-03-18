from unittest.mock import Mock, create_autospec

import pytest

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.in_process import InProcessResolver
from openfeature.contrib.provider.flagd.resolvers.process.flags import Flag, FlagStore
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError, ParseError


def targeting():
    return {
        "if": [
            {"==": [{"var": "targetingKey"}, "target_variant"]},
            "target_variant",
            None,
        ]
    }


def context(targeting_key):
    return EvaluationContext(targeting_key=targeting_key)


@pytest.fixture
def config():
    return create_autospec(Config)


@pytest.fixture
def flag_store():
    return create_autospec(FlagStore)


@pytest.fixture
def flag():
    return Flag(
        key="flag",
        state="ENABLED",
        variants={"default_variant": False, "target_variant": True},
        default_variant="default_variant",
        targeting=targeting(),
    )


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
    resolver.flag_store.get_flag = Mock(return_value=None)
    with pytest.raises(FlagNotFoundError):
        resolver.resolve_boolean_details("nonexistent_flag", False)


def test_resolve_boolean_details_disabled_flag(flag, resolver):
    flag.state = "DISABLED"
    resolver.flag_store.get_flag = Mock(return_value=flag)

    result = resolver.resolve_boolean_details("disabled_flag", False)

    assert result.reason == "DISABLED"
    assert result.variant is None
    assert not result.value


def test_resolve_boolean_details_invalid_variant(resolver, flag):
    flag.targeting = {"var": ["targetingKey", "invalid_variant"]}

    resolver.flag_store.get_flag = Mock(return_value=flag)

    with pytest.raises(ParseError):
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
                "targeting": targeting(),
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
    flag,
    input_config,
    resolve_config,
    expected,
):
    flag.variants = input_config["variants"]
    flag.targeting = input_config["targeting"]
    resolver.flag_store.get_flag = Mock(return_value=flag)

    result = getattr(resolver, resolve_config["method"])(
        "flag", resolve_config["default_value"], resolve_config["context"]
    )

    assert result.reason == expected["reason"]
    assert result.variant == expected["variant"]
    assert result.value == expected["value"]
