import json
import os

import pytest
from src.openfeature.contrib.provider.envvar import EnvVarProvider

from openfeature.exception import FlagNotFoundError, ParseError


def test_unknown_flag_key_throws_flag_not_found_error():
    provider = EnvVarProvider()
    with pytest.raises(FlagNotFoundError):
        provider.resolve_boolean_details("unknown_flag_key", True, None)


def test_string_flag_evaluates_the_flag():
    key = "test-flag-key"
    value = "test-value"
    os.environ[key] = value

    provider = EnvVarProvider()
    result = provider.resolve_string_details(key, True, None)

    assert result.value == value


def test_int_flag_evaluates_the_flag():
    key = "test-flag-key"
    value = 324
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_integer_details(key, True, None)

    assert result.value == value


def test_float_flag_evaluates_the_flag():
    key = "test-flag-key"
    value = 324.34
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_float_details(key, True, None)

    assert result.value == value


def test_boolean_flag_evaluates_the_flag():
    key = "test-flag-key"
    value = True
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_boolean_details(key, True, None)

    assert result.value == value


def test_object_flag_evaluates_the_flag():
    key = "test-flag-key"
    value = {"a": 23}
    os.environ[key] = str(json.dumps(value))

    provider = EnvVarProvider()
    result = provider.resolve_object_details(key, True, None)

    assert result.value == value


def test_int_flag_with_invalid_format_raises_exception():
    key = "test-flag-key"
    value = "23.23"
    os.environ[key] = str(value)

    provider = EnvVarProvider()

    with pytest.raises(ParseError):
        provider.resolve_integer_details(key, True, None)


def test_object_flag_with_invalid_json_object_raises_an_error():
    key = "test-flag-key"
    value = 23
    os.environ[key] = str(json.dumps(value))

    provider = EnvVarProvider()

    with pytest.raises(ParseError):
        provider.resolve_object_details(key, True, None)


def test_provider_returns_correct_metadata():
    provider = EnvVarProvider()
    metadata = provider.get_metadata()
    assert metadata is not None
    assert metadata.name == "EnvVarProvider"
