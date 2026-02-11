"""Unit tests for parsers module."""

import pytest

from openfeature.contrib.provider.awsssm.parsers import (
    parse_boolean,
    parse_float,
    parse_integer,
    parse_object,
)
from openfeature.exception import ParseError, TypeMismatchError


class TestParseBoolean:
    """Tests for parse_boolean function."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("true", True),
            ("false", False),
            ("TRUE", True),
            ("FALSE", False),
            ("True", True),
            ("False", False),
            ("TrUe", True),
            ("FaLsE", False),
            ("  true  ", True),
            ("  false  ", False),
        ],
    )
    def test_parse_boolean_valid_inputs(self, value, expected):
        assert parse_boolean(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "yes",
            "no",
            "1",
            "0",
            "t",
            "f",
            "on",
            "off",
            "enabled",
            "disabled",
            "abc",
            "",
            "truee",
            "falsee",
        ],
    )
    def test_parse_boolean_invalid_inputs(self, value):
        with pytest.raises(TypeMismatchError) as exc_info:
            parse_boolean(value)
        assert "Expected 'true' or 'false'" in str(exc_info.value)
        assert value in str(exc_info.value)


class TestParseInteger:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("0", 0),
            ("1", 1),
            ("-1", -1),
            ("42", 42),
            ("-123", -123),
            ("999999", 999999),
            ("-999999", -999999),
        ],
    )
    def test_parse_integer_valid_inputs(self, value, expected):
        assert parse_integer(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "abc",
            "1.5",
            "3.14",
            "",
            "12.0",
            "1e5",
            "0x10",
            "ten",
            "1,000",
        ],
    )
    def test_parse_integer_invalid_inputs(self, value):
        with pytest.raises(TypeMismatchError) as exc_info:
            parse_integer(value)
        assert "Cannot parse" in str(exc_info.value)
        assert "as integer" in str(exc_info.value)
        assert value in str(exc_info.value)


class TestParseFloat:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("0", 0.0),
            ("0.0", 0.0),
            ("1", 1.0),
            ("-1", -1.0),
            ("3.14", 3.14),
            ("-2.5", -2.5),
            ("1.23456789", 1.23456789),
            ("-0.001", -0.001),
            ("1e5", 1e5),
            ("1.5e-3", 1.5e-3),
            ("-2.3e10", -2.3e10),
        ],
    )
    def test_parse_float_valid_inputs(self, value, expected):
        assert parse_float(value) == pytest.approx(expected)

    @pytest.mark.parametrize(
        "value",
        [
            "abc",
            "",
            "not-a-number",
            "1,000.5",
        ],
    )
    def test_parse_float_invalid_inputs(self, value):
        with pytest.raises(TypeMismatchError) as exc_info:
            parse_float(value)
        assert "Cannot parse" in str(exc_info.value)
        assert "as float" in str(exc_info.value)
        assert value in str(exc_info.value)


class TestParseObject:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ('{"key": "value"}', {"key": "value"}),
            ('{"number": 42}', {"number": 42}),
            ('{"key": "value", "number": 42}', {"key": "value", "number": 42}),
            ('{"nested": {"key": "value"}}', {"nested": {"key": "value"}}),
            ('{"array": [1, 2, 3]}', {"array": [1, 2, 3]}),
            ("{}", {}),
        ],
    )
    def test_parse_object_valid_json_objects(self, value, expected):
        assert parse_object(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("[1, 2, 3]", [1, 2, 3]),
            ('["a", "b", "c"]', ["a", "b", "c"]),
            ('[{"key": "value"}]', [{"key": "value"}]),
            ("[]", []),
        ],
    )
    def test_parse_object_valid_json_arrays(self, value, expected):
        assert parse_object(value) == expected

    @pytest.mark.parametrize(
        "value",
        [
            "not json",
            "{invalid}",
            '{"key": value}',
            '{"key": "value"',
            '{"key": "value"}extra',
            "",
        ],
    )
    def test_parse_object_invalid_json(self, value):
        with pytest.raises(ParseError) as exc_info:
            parse_object(value)
        assert "Invalid JSON" in str(exc_info.value)

    @pytest.mark.parametrize(
        "value",
        [
            "42",
            '"string"',
            "true",
            "false",
            "null",
        ],
    )
    def test_parse_object_non_object_json(self, value):
        with pytest.raises(ParseError) as exc_info:
            parse_object(value)
        assert "Expected JSON object or array" in str(exc_info.value)
