import json
import typing


def str2bool(v: str) -> bool:
    return v.lower() in ("yes", "true", "t", "1")


type_cast: dict[str, typing.Callable] = {
    "Integer": int,
    "Float": float,
    "String": str,
    "Boolean": str2bool,
    # Gherkin uses \" to escape quotes in table cells; pytest-bdd preserves the
    # backslash, so we strip it before feeding the string to json.loads.
    "Object": lambda v: json.loads(v.replace('\\\\"', '"')),
}

JsonObject = dict | list
JsonPrimitive = str | bool | float | int | JsonObject
