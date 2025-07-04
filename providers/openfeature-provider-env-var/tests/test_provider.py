import os

import pytest
from openfeature.exception import FlagNotFoundError

from src.openfeature.contrib.provider.envvar import EnvVarProvider


def test_unknown_flag_key_throws_flag_not_found_error():
    provider = EnvVarProvider()
    with pytest.raises(FlagNotFoundError):
        provider.resolve_boolean_details("unknown_flag_key", True, None)


def test_known_flag_key_evaluates_the_flag():
    key = "test-flag-key"
    value = "test-value"
    os.environ[key] = value

    provider = EnvVarProvider()
    result = provider.resolve_string_details(key, True, None)

    assert result.value == value
