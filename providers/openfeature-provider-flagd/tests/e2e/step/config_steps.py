import re
import typing

import pytest
from asserts import assert_equal, assert_true
from pytest_bdd import given, parsers, then, when

from openfeature.contrib.provider.flagd.config import CacheType, Config, ResolverType


def camel_to_snake(name):
    name = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


def convert_resolver_type(val: typing.Union[str, ResolverType]) -> ResolverType:
    if isinstance(val, str):
        v = val.lower()
        return ResolverType(v)
    else:
        return ResolverType(val)


type_cast = {
    "Integer": int,
    "Long": int,
    "String": str,
    "Boolean": str2bool,
    "ResolverType": convert_resolver_type,
    "CacheType": CacheType,
}


@pytest.fixture()
def option_values() -> dict:
    return {}


@given(
    parsers.cfparse(
        'an option "{option}" of type "{type_info}" with value "{value}"',
    ),
)
def option_with_value(option: str, value: str, type_info: str, option_values: dict):
    value = type_cast[type_info](value)
    option_values[camel_to_snake(option)] = value


@given(
    parsers.cfparse(
        'an environment variable "{env}" with value "{value}"',
    ),
)
def env_with_value(monkeypatch, env: str, value: str):
    monkeypatch.setenv(env, value)


@when(
    parsers.cfparse(
        "a config was initialized",
    ),
    target_fixture="config_or_error",
)
def initialize_config(option_values):
    try:
        return Config(**option_values), False
    except AttributeError:
        return None, True


@when(
    parsers.cfparse(
        'a config was initialized for "{resolver_type}"',
    ),
    target_fixture="config_or_error",
)
def initialize_config_for(resolver_type: str, option_values: dict):
    try:
        return Config(resolver=ResolverType(resolver_type), **option_values), False
    except AttributeError:
        return None, True


@then(
    parsers.cfparse(
        'the option "{option}" of type "{type_info}" should have the value "{value}"',
    )
)
def check_option_value(option, value, type_info, config_or_error):
    value = type_cast[type_info](value)
    value = value if value != "null" else None
    config, _ = config_or_error
    assert_equal(config.__getattribute__(camel_to_snake(option)), value)


@then(
    parsers.cfparse(
        "we should have an error",
    )
)
def check_option_error(config_or_error):
    _, error = config_or_error
    assert_true(error)
