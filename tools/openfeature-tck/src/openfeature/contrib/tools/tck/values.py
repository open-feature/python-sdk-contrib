"""Turning Gherkin strings into typed values, and comparing them with what a provider resolved."""

from __future__ import annotations

import json
import typing

from openfeature.flag_evaluation import FlagType

__all__ = ["describe", "parse_flag_type", "parse_value", "values_equal"]

_BY_NAME: dict[str, FlagType] = {
    "boolean": FlagType.BOOLEAN,
    "string": FlagType.STRING,
    "integer": FlagType.INTEGER,
    "float": FlagType.FLOAT,
    "object": FlagType.OBJECT,
}


def parse_flag_type(raw: str) -> FlagType:
    """Resolve the type named in a scenario, case-insensitively."""
    try:
        return _BY_NAME[raw.strip().lower()]
    except KeyError:
        names = ", ".join(sorted(n.capitalize() for n in _BY_NAME))
        msg = f"unknown flag type {raw!r}: expected one of {names}"
        raise ValueError(msg) from None


def _parse_bool(raw: str) -> bool:
    lowered = raw.strip().lower()
    if lowered in {"true", "t", "yes", "1"}:
        return True
    if lowered in {"false", "f", "no", "0"}:
        return False
    msg = f"{raw!r} is not a boolean"
    raise ValueError(msg)


def parse_value(flag_type: FlagType, raw: str) -> typing.Any:
    """Convert a value written in a scenario into the type the API uses.

    Everything in Gherkin is a string, so this is where ``"0.5"`` becomes a
    float and ``"{}"`` becomes an empty object. Parsing per declared type rather
    than guessing is what keeps the integer and float scenarios
    distinguishable: ``"1"`` is an ``int`` in an Integer scenario and a ``float``
    in a Float one.
    """
    if flag_type is FlagType.BOOLEAN:
        return _parse_bool(raw)
    if flag_type is FlagType.STRING:
        return raw
    if flag_type is FlagType.INTEGER:
        return int(raw)
    if flag_type is FlagType.FLOAT:
        return float(raw)
    if flag_type is FlagType.OBJECT:
        # Gherkin escapes quotes in table cells; pytest-bdd keeps the backslash,
        # so strip it before handing the text to json.
        return json.loads(raw.replace('\\"', '"'))
    msg = f"unknown flag type {flag_type!r}"
    raise ValueError(msg)


def _as_number(value: typing.Any) -> float | None:
    """Return a numeric value as a float, or None if it is not numeric.

    Booleans are deliberately excluded. Python makes ``bool`` a subclass of
    ``int``, so an unguarded numeric comparison would quietly report ``True`` and
    ``1`` as equal -- which is the exact confusion several of these scenarios
    exist to detect.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def values_equal(expected: typing.Any, actual: typing.Any) -> bool:
    """Compare an expected value from a scenario with what a provider resolved.

    Numbers are compared numerically rather than by Python type. A provider that
    deserialises its backend's JSON hands back ``float`` for every number, so the
    ``100`` inside ``object-flag`` arrives as ``100.0`` from one provider and
    ``100`` from another while both are correct. Type distinctness is asserted
    where it belongs -- by requesting a flag as a specific type and checking the
    error code -- not by accident of how a number was decoded.
    """
    # A boolean only ever equals a boolean. Without this, Python's bool-is-an-int
    # rule would make True == 1 and quietly satisfy the scenario that exists to
    # catch exactly that confusion.
    if isinstance(expected, bool) or isinstance(actual, bool):
        return (
            isinstance(expected, bool)
            and isinstance(actual, bool)
            and expected == actual
        )

    expected_number = _as_number(expected)
    if expected_number is not None:
        actual_number = _as_number(actual)
        return actual_number is not None and expected_number == actual_number

    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            return False
        return all(values_equal(v, actual[k]) for k, v in expected.items())

    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            values_equal(e, a) for e, a in zip(expected, actual, strict=True)
        )

    return bool(expected == actual)


def describe(value: typing.Any) -> str:
    """Render a value for a failure message, including its type.

    "expected 100 but got 100" is the single most confusing failure a
    cross-language conformance suite can produce.
    """
    return f"{value!r} ({type(value).__name__})"
