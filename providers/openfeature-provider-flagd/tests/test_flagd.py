from numbers import Number

import pytest

from openfeature.contrib.provider.flagd import FlagdProvider


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
    flag = client.get_object_details(flag_key="Key", default_value=return_value)

    # Then
    assert flag is not None
    assert flag.value == return_value
    assert isinstance(flag.value, dict)


def test_get_metadata_returns_metadata_object_with_name():
    provider = FlagdProvider()
    metadata = provider.get_metadata()
    assert metadata.name == "FlagdProvider"


@pytest.mark.asyncio
async def test_should_get_boolean_flag_from_flagd_async(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = await client.get_boolean_details_async(flag_key="Key", default_value=True)

    # Then
    assert flag is not None
    assert flag.value
    assert isinstance(flag.value, bool)


@pytest.mark.asyncio
async def test_should_get_integer_flag_from_flagd_async(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = await client.get_integer_details_async(flag_key="Key", default_value=100)

    # Then
    assert flag is not None
    assert flag.value == 100
    assert isinstance(flag.value, Number)


@pytest.mark.asyncio
async def test_should_get_float_flag_from_flagd_async(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = await client.get_float_details_async(flag_key="Key", default_value=100.0)

    # Then
    assert flag is not None
    assert flag.value == 100.0
    assert isinstance(flag.value, Number)


@pytest.mark.asyncio
async def test_should_get_string_flag_from_flagd_async(flagd_provider_client):
    # Given
    client = flagd_provider_client

    # When
    flag = await client.get_string_details_async(flag_key="Key", default_value="String")

    # Then
    assert flag is not None
    assert flag.value == "String"
    assert isinstance(flag.value, str)


@pytest.mark.asyncio
async def test_should_get_object_flag_from_flagd_async(flagd_provider_client):
    # Given
    client = flagd_provider_client
    return_value = {
        "String": "string",
        "Number": 2,
        "Boolean": True,
    }

    # When
    flag = await client.get_object_details_async(
        flag_key="Key", default_value=return_value
    )

    # Then
    assert flag is not None
    assert flag.value == return_value
    assert isinstance(flag.value, dict)
