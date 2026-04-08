import json
import typing


def str2bool(v: str) -> bool:
    return v.lower() in ("yes", "true", "t", "1")


type_cast: typing.Dict[str, typing.Callable] = {
    "Integer": int,
    "Float": float,
    "String": str,
    "Boolean": str2bool,
    "Object": lambda v: json.loads(v.replace('\\\\"', '"')),
}

JsonObject = typing.Union[dict, list]
JsonPrimitive = typing.Union[str, bool, float, int, JsonObject]
