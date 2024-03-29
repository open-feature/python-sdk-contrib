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

    hash_key = data.get("$flagd", {}).get("flagKey", "") + bucket_by
    hash_ratio = abs(mmh3.hash(hash_key)) / (2**31 - 1)
    bucket = int(hash_ratio * 100)

    range_end = 0
    for variant, weight in arr:
        range_end += weight
        if bucket < range_end:
            return variant

    return None
