import json
import time
import typing

from asserts import assert_true


def str2bool(v):
    return v.lower() in ("yes", "true", "t", "1")


type_cast = {
    "Integer": int,
    "Float": float,
    "String": str,
    "Boolean": str2bool,
    "Object": json.loads,
}


JsonObject = typing.Union[dict, list]
JsonPrimitive = typing.Union[str, bool, float, int, JsonObject]


def wait_for(pred, poll_sec=2, timeout_sec=10):
    start = time.time()
    while not (ok := pred()) and (time.time() - start < timeout_sec):
        time.sleep(poll_sec)
    assert_true(pred())
    return ok
