"""Smoke tests to verify the testkit package can be imported and used."""

import json

from openfeature.contrib.tools.flagd.testkit import (
    get_features_path,
    load_testkit_flags,
)


def test_load_testkit_flags_returns_valid_json():
    raw = load_testkit_flags()
    data = json.loads(raw)
    assert isinstance(data, dict), "testkit flags should be a JSON object"
    assert "flags" in data, "testkit flags should contain a 'flags' key"


def test_get_features_path_is_non_empty_string():
    path = get_features_path()
    assert isinstance(path, str)
    assert len(path) > 0
