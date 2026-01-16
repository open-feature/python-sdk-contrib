import json
from typing import Any, Union

from openfeature.exception import ParseError, TypeMismatchError


def parse_boolean(value: str) -> bool:
    """
    Parse a string value as a boolean.

    Args:
        value: The string value

    Returns:
        The parsed boolean value

    Raises:
        TypeMismatchError: If the value is not 'true' or 'false'
    """
    lower_value = value.lower().strip()
    if lower_value == "true":
        return True
    if lower_value == "false":
        return False
    raise TypeMismatchError(
        f"Expected 'true' or 'false' for boolean flag, got '{value}'"
    )


def parse_integer(value: str) -> int:
    """
    Parse a string value as an integer.

    Args:
        value: The string value

    Returns:
        The parsed integer value

    Raises:
        TypeMismatchError: If the value cannot be parsed as an integer
    """
    try:
        return int(value)
    except ValueError as e:
        raise TypeMismatchError(f"Cannot parse '{value}' as integer") from e


def parse_float(value: str) -> float:
    """
    Parse a string value as a float.

    Args:
        value: The string value

    Returns:
        The parsed float value

    Raises:
        TypeMismatchError: If the value cannot be parsed as a float
    """
    try:
        return float(value)
    except ValueError as e:
        raise TypeMismatchError(f"Cannot parse '{value}' as float") from e


def parse_object(value: str) -> Union[dict[str, Any], list[Any]]:
    """
    Parse a string value as a JSON object.

    Args:
        value: The string value containing JSON

    Returns:
        The parsed object (dict or list)

    Raises:
        ParseError: If the value is not valid JSON
    """
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, (dict, list)):
            raise ParseError(
                f"Expected JSON object or array, got {type(parsed).__name__}"
            )
        return parsed
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}") from e
