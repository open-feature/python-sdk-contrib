import logging
import typing

import mmh3
import semver

JsonPrimitive = typing.Union[str, bool, float, int]
JsonLogicArg = typing.Union[JsonPrimitive, tuple[JsonPrimitive]]


def fractional(data: dict, *args: JsonLogicArg) -> typing.Optional[str]:
    if not args:
        raise ValueError("No arguments provided to fractional operator.")

    bucket_by = None
    if isinstance(args[0], str):
        bucket_by = args[0]
        args = args[1:]
    else:
        bucket_by = data.get("targetingKey")

    if not bucket_by:
        return None

    seed = data.get("$flagd", {}).get("flagKey", "")
    hash_key = seed + bucket_by
    hash_ratio = abs(mmh3.hash(hash_key)) / (2**31 - 1)
    bucket = int(hash_ratio * 100)

    for arg in args:
        if (
            not isinstance(arg, (tuple, list))
            or len(arg) != 2
            or not isinstance(arg[0], str)
            or not isinstance(arg[1], int)
        ):
            raise ValueError("Fractional variant weights must be (str, int) tuple")
    variant_weights: tuple[tuple[str, int]] = args  # type: ignore[assignment]

    range_end = 0
    for variant, weight in variant_weights:
        range_end += weight
        if bucket < range_end:
            return variant

    return None


def starts_with(data: dict, *args: JsonLogicArg) -> bool:
    def f(s1: str, s2: str) -> bool:
        return s1.startswith(s2)

    return string_comp(f, data, *args)


def ends_with(data: dict, *args: JsonLogicArg) -> bool:
    def f(s1: str, s2: str) -> bool:
        return s1.endswith(s2)

    return string_comp(f, data, *args)


def string_comp(
    comparator: typing.Callable[[str, str], bool], data: dict, *args: JsonLogicArg
) -> bool:
    if not args:
        raise ValueError("No arguments provided to string_comp operator.")
    if len(args) != 2:
        raise ValueError("Exactly 2 args expected for string_comp operator.")
    arg1, arg2 = args
    if not isinstance(arg1, str):
        logging.debug(f"incorrect argument for first argument, expected string: {arg1}")
        return False
    if not isinstance(arg2, str):
        logging.debug(
            f"incorrect argument for second argument, expected string: {arg2}"
        )
        return False

    return comparator(arg1, arg2)


def sem_ver(data: dict, *args: JsonLogicArg) -> bool:  # noqa: C901
    if not args:
        raise ValueError("No arguments provided to sem_ver operator.")
    if len(args) != 3:
        raise ValueError("Exactly 3 args expected for sem_ver operator.")

    arg1, op, arg2 = args

    try:
        v1 = semver.Version.parse(arg1)
        v2 = semver.Version.parse(arg2)
    except ValueError as e:
        logging.exception(e)
        return False

    if op == "=":
        return v1 == v2  # type: ignore[no-any-return]
    elif op == "!=":
        return v1 != v2  # type: ignore[no-any-return]
    elif op == "<":
        return v1 < v2  # type: ignore[no-any-return]
    elif op == "<=":
        return v1 <= v2  # type: ignore[no-any-return]
    elif op == ">":
        return v1 > v2  # type: ignore[no-any-return]
    elif op == ">=":
        return v1 >= v2  # type: ignore[no-any-return]
    elif op == "^":
        return v1.major == v2.major  # type: ignore[no-any-return]
    elif op == "~":
        return v1.major == v2.major and v1.minor == v2.minor  # type: ignore[no-any-return]
    else:
        raise ValueError(f"Op not supported by sem_ver: {op}")
