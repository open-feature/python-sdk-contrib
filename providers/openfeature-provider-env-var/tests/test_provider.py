import json
import os

import pytest
from openfeature.exception import FlagNotFoundError

from src.openfeature.contrib.provider.envvar import EnvVarProvider


def test_unknown_flag_key_throws_flag_not_found_error():
    provider = EnvVarProvider()
    with pytest.raises(FlagNotFoundError):
        provider.resolve_boolean_details("unknown_flag_key", True, None)


def test_string_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = "test-value"
    os.environ[key] = value

    provider = EnvVarProvider()
    result = provider.resolve_string_details(key, True, None)

    assert result.value == value


def test_int_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = 324
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_integer_details(key, True, None)

    assert result.value == value


def test_float_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = 324.34
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_float_details(key, True, None)

    assert result.value == value


def test_boolean_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = True
    os.environ[key] = str(value)

    provider = EnvVarProvider()
    result = provider.resolve_boolean_details(key, True, None)

    assert result.value == value


def test_object_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = {"a": 23}
    os.environ[key] = str(json.dumps(value))

    provider = EnvVarProvider()
    result = provider.resolve_object_details(key, True, None)

    assert result.value == value


def test_provider_returns_correct_metadata():
    provider = EnvVarProvider()
    metadata = provider.get_metadata()
    assert metadata is not None
    assert metadata.name == "EnvVarProvider"
