from numbers import Number

from openfeature import api
from openfeature.contrib.providers.flagd import FlagdProvider


def setup():
    api.set_provider(FlagdProvider())
    provider = api.get_provider()
    assert isinstance(provider, FlagdProvider)


def test_should_get_boolean_flag_from_flagd(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = client.get_boolean_details(flag_key="Key", default_value=True)

    # Then
    assert flag is not None
    assert flag.value
    assert isinstance(flag.value, bool)


def test_should_get_integer_flag_from_flagd(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = client.get_integer_details(flag_key="Key", default_value=100)

    # Then
    assert flag is not None
    assert flag.value == 100
    assert isinstance(flag.value, Number)


def test_should_get_float_flag_from_flagd(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = client.get_float_details(flag_key="Key", default_value=100)

    # Then
    assert flag is not None
    assert flag.value == 100
    assert isinstance(flag.value, Number)


def test_should_get_string_flag_from_flagd(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = client.get_string_details(flag_key="Key", default_value="String")

    # Then
    assert flag is not None
    assert flag.value == "String"
    assert isinstance(flag.value, str)


def test_should_get_object_flag_from_flagd(flagd_provider_client):
    # Given
    client = flagd_provider_client
    return_value = {
        "String": "string",
        "Number": 2,
        "Boolean": True,
    }

    # When
    flag = client.get_string_details(flag_key="Key", default_value=return_value)

    # Then
    assert flag is not None
    assert flag.value == return_value
    assert isinstance(flag.value, dict)
