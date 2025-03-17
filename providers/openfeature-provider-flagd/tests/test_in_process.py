from unittest.mock import Mock, create_autospec

import pytest

from openfeature.contrib.provider.flagd.config import Config
from openfeature.contrib.provider.flagd.resolvers.in_process import InProcessResolver
from openfeature.contrib.provider.flagd.resolvers.process.flags import Flag, FlagStore
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError, ParseError


@pytest.fixture
def config():
    return create_autospec(Config)


@pytest.fixture
def flag_store():
    return create_autospec(FlagStore)


@pytest.fixture
def targeting():
    return {
        "if": [
            {"==": [{"var": "targetingKey"}, "target_variant"]},
            "target_variant",
            None,
        ]
    }


@pytest.fixture
def flag(targeting):
    return Flag(
        key="flag",
        state="ENABLED",
        variants={"default_variant": False, "target_variant": True},
        default_variant="default_variant",
        targeting=targeting,
    )


@pytest.fixture
def context():
    return EvaluationContext(targeting_key="target_variant")


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


@pytest.fixture
def flag():
    return Flag(
        key="flag",
        state="ENABLED",
        variants={"default_variant": False},
        default_variant="default_variant",
        targeting=None,
    )


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


def test_resolve_boolean_details_flag_not_found(resolver):
    resolver.flag_store.get_flag = Mock(return_value=None)
    with pytest.raises(FlagNotFoundError):
        resolver.resolve_boolean_details("nonexistent_flag", False)


def test_resolve_boolean_details_disabled_flag(flag, resolver):
    flag.state = "DISABLED"
    resolver.flag_store.get_flag = Mock(return_value=flag)

    result = resolver.resolve_boolean_details("disabled_flag", False)

    assert result.reason == "DISABLED"
    assert result.variant == None
    assert result.value == False


def test_resolve_boolean_details_invalid_variant(resolver, flag):
    flag.targeting = {"var": ["targetingKey", "invalid_variant"]}

    resolver.flag_store.get_flag = Mock(return_value=flag)

    with pytest.raises(ParseError):
        resolver.resolve_boolean_details("flag", False)


@pytest.mark.parametrize(
    "variants, targeting,"
    "context, method, default_value,"
    "expected_reason, expected_variant, expected_value,",
    [
        (
            {"default_variant": False, "target_variant": True},
            None,
            None,
            "resolve_boolean_details",
            False,
            "STATIC",
            "default_variant",
            False,
        ),
        (
            {"default_variant": False, "target_variant": True},
            targeting(),
            context("no_target_variant"),
            "resolve_boolean_details",
            False,
            "DEFAULT",
            "default_variant",
            False,
        ),
        (
            {"default_variant": False, "target_variant": True},
            targeting(),
            context("target_variant"),
            "resolve_boolean_details",
            False,
            "TARGETING_MATCH",
            "target_variant",
            True,
        ),
        (
            {"default_variant": "default", "target_variant": "target"},
            targeting(),
            context("target_variant"),
            "resolve_string_details",
            "placeholder",
            "TARGETING_MATCH",
            "target_variant",
            "target",
        ),
        (
            {"default_variant": 1.0, "target_variant": 2.0},
            targeting(),
            context("target_variant"),
            "resolve_float_details",
            0.0,
            "TARGETING_MATCH",
            "target_variant",
            2.0,
        ),
        (
            {"default_variant": True, "target_variant": False},
            targeting(),
            context("target_variant"),
            "resolve_boolean_details",
            True,
            "TARGETING_MATCH",
            "target_variant",
            False,
        ),
        (
            {"default_variant": 10, "target_variant": 0},
            targeting(),
            context("target_variant"),
            "resolve_integer_details",
            1,
            "TARGETING_MATCH",
            "target_variant",
            0,
        ),
        (
            {"default_variant": {}, "target_variant": {}},
            targeting(),
            context("target_variant"),
            "resolve_object_details",
            {},
            "TARGETING_MATCH",
            "target_variant",
            {},
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
    variants,
    targeting,
    context,
    method,
    default_value,
    expected_reason,
    expected_variant,
    expected_value,
):
    flag.variants = variants
    flag.targeting = targeting
    resolver.flag_store.get_flag = Mock(return_value=flag)

    result = getattr(resolver, method)("flag", default_value, context)

    assert result.reason == expected_reason
    assert result.variant == expected_variant
    assert result.value == expected_value
