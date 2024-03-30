import logging
import typing

import mmh3


def fractional(data: dict, *arr: tuple[str, int]) -> typing.Optional[str]:
    bucket_by = None
    if isinstance(arr[0], str):
        bucket_by = arr[0]
        arr = arr[1:]
    else:
        bucket_by = data.get("targetingKey")

    if not bucket_by:
        return None

    seed = data.get("$flagd", {}).get("flagKey", "")
    hash_key = seed + bucket_by
    hash_ratio = abs(mmh3.hash(hash_key)) / (2**31 - 1)
    bucket = int(hash_ratio * 100)

    range_end = 0
    for variant, weight in arr:
        range_end += weight
        if bucket < range_end:
            return variant

    return None


def starts_with(data: dict, arg1: str, arg2: str) -> bool:
    if not isinstance(arg1, str):
        logging.debug(f"incorrect argument for first argument, expected string: {arg1}")
        return False
    if not isinstance(arg2, str):
        logging.debug(
            f"incorrect argument for second argument, expected string: {arg2}"
        )
        return False
    return arg1.startswith(arg2)


def ends_with(data: dict, arg1: str, arg2: str) -> bool:
    if not isinstance(arg1, str):
        logging.debug(f"incorrect argument for first argument, expected string: {arg1}")
        return False
    if not isinstance(arg2, str):
        logging.debug(
            f"incorrect argument for second argument, expected string: {arg2}"
        )
        return False
    return arg1.endswith(arg2)
