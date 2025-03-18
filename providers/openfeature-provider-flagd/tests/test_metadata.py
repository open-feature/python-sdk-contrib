import os
import time
from time import sleep

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.contrib.provider.flagd.resolvers.process.flags import (
    _validate_metadata,
)
from openfeature.event import EventDetails, ProviderEvent
from openfeature.exception import ErrorCode, ParseError


def create_client(file_name):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "./flags/"))
    provider = FlagdProvider(
        resolver_type=ResolverType.FILE,
        offline_flag_source_path=f"{path}/{file_name}",
    )

    api.set_provider(provider)
    return api.get_client()


def test_should_load_flag_set_metadata():
    client = create_client("basic-flag-set-metadata.json")
    res = client.get_boolean_details("basic-flag", False)

    assert res.flag_metadata is not None
    assert isinstance(res.flag_metadata, dict)
    assert len(res.flag_metadata) == 4
    assert res.flag_metadata["string"] == "a"
    assert res.flag_metadata["integer"] == 1
    assert res.flag_metadata["float"] == 1.2
    assert res.flag_metadata["bool"]


def test_should_load_flag_metadata():
    client = create_client("basic-flag-metadata.json")
    res = client.get_boolean_details("basic-flag", False)

    assert res.flag_metadata is not None
    assert isinstance(res.flag_metadata, dict)
    assert len(res.flag_metadata) == 4
    assert res.flag_metadata["string"] == "a"
    assert res.flag_metadata["integer"] == 1
    assert res.flag_metadata["float"] == 1.2
    assert res.flag_metadata["bool"]


def test_should_load_flag_combined_metadata():
    client = create_client("basic-flag-combined-metadata.json")
    res = client.get_boolean_details("basic-flag", False)

    assert res.flag_metadata is not None
    assert isinstance(res.flag_metadata, dict)
    assert len(res.flag_metadata) == 8
    assert res.flag_metadata["string"] == "a"
    assert res.flag_metadata["integer"] == 1
    assert res.flag_metadata["float"] == 1.2
    assert res.flag_metadata["bool"]
    assert res.flag_metadata["flag-set-string"] == "c"
    assert res.flag_metadata["flag-set-integer"] == 3
    assert res.flag_metadata["flag-set-float"] == 3.2
    assert not res.flag_metadata["flag-set-bool"]


class Channel:
    parse_error_received = False


def create_error_handler():
    channel = Channel()

    def error_handler(details: EventDetails):
        nonlocal channel
        if details.error_code == ErrorCode.PARSE_ERROR:
            channel.parse_error_received = True

    return error_handler, channel


@pytest.mark.parametrize(
    "file_name",
    [
        "invalid-flag-set-metadata.json",
        "invalid-flag-set-metadata-list.json",
        "invalid-flag-metadata.json",
        "invalid-flag-metadata-list.json",
    ],
)
def test_invalid_flag_set_metadata(file_name):
    error_handler, channel = create_error_handler()

    client = create_client(file_name)
    client.add_handler(ProviderEvent.PROVIDER_ERROR, error_handler)

    # keep the test thread alive
    max_timeout = 2
    start = time.time()
    while not channel.parse_error_received:
        now = time.time()
        if now - start > max_timeout:
            raise AssertionError()
        sleep(0.01)


def test_validate_metadata_with_none_key():
    try:
        _validate_metadata(None, "a")
    except ParseError:
        return
    raise AssertionError()


def test_validate_metadata_with_empty_key():
    try:
        _validate_metadata("", "a")
    except ParseError:
        return
    raise AssertionError()


def test_validate_metadata_with_non_string_key():
    try:
        _validate_metadata(1, "a")
    except ParseError:
        return
    raise AssertionError()


def test_validate_metadata_with_non_string_value():
    try:
        _validate_metadata("a", [])
    except ParseError:
        return
    raise AssertionError()


def test_validate_metadata_with_none_value():
    try:
        _validate_metadata("a", None)
    except ParseError:
        return
    raise AssertionError()
