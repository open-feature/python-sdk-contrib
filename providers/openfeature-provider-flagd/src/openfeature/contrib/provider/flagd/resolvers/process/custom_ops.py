import logging
import typing

import mmh3
import semver

JsonPrimitive = typing.Union[str, bool, float, int]
JsonLogicArg = typing.Union[JsonPrimitive, typing.Sequence[JsonPrimitive]]

logger = logging.getLogger("openfeature.contrib")


def fractional(data: dict, *args: JsonLogicArg) -> typing.Optional[str]:
    if not args:
        logger.error("No arguments provided to fractional operator.")
        return None

    bucket_by = None
    if isinstance(args[0], str):
        bucket_by = args[0]
        args = args[1:]
    else:
        seed = data.get("$flagd", {}).get("flagKey", "")
        targeting_key = data.get("targetingKey")
        if not targeting_key:
            logger.error("No targetingKey provided for fractional shorthand syntax.")
            return None
        bucket_by = seed + targeting_key

    if not bucket_by:
        logger.error("No hashKey value resolved")
        return None

    hash_ratio = abs(mmh3.hash(bucket_by)) / (2**31 - 1)
    bucket = int(hash_ratio * 100)

    for arg in args:
        if (
            not isinstance(arg, (tuple, list))
            or len(arg) != 2
            or not isinstance(arg[0], str)
            or not isinstance(arg[1], int)
        ):
            logger.error("Fractional variant weights must be (str, int) tuple")
            return None
    variant_weights: typing.Tuple[typing.Tuple[str, int]] = args  # type: ignore[assignment]

    range_end = 0
    for variant, weight in variant_weights:
        range_end += weight
        if bucket < range_end:
            return variant

    return None


def starts_with(data: dict, *args: JsonLogicArg) -> typing.Optional[bool]:
    def f(s1: str, s2: str) -> bool:
        return s1.startswith(s2)

    return string_comp(f, data, *args)


def ends_with(data: dict, *args: JsonLogicArg) -> typing.Optional[bool]:
    def f(s1: str, s2: str) -> bool:
        return s1.endswith(s2)

    return string_comp(f, data, *args)


def string_comp(
    comparator: typing.Callable[[str, str], bool], data: dict, *args: JsonLogicArg
) -> typing.Optional[bool]:
    if not args:
        logger.error("No arguments provided to string_comp operator.")
        return None
    if len(args) != 2:
        logger.error("Exactly 2 args expected for string_comp operator.")
        return None
    arg1, arg2 = args
    if not isinstance(arg1, str):
        logger.debug(f"incorrect argument for first argument, expected string: {arg1}")
        return False
    if not isinstance(arg2, str):
        logger.debug(f"incorrect argument for second argument, expected string: {arg2}")
        return False

    return comparator(arg1, arg2)


def sem_ver(data: dict, *args: JsonLogicArg) -> typing.Optional[bool]:  # noqa: C901
    if not args:
        logger.error("No arguments provided to sem_ver operator.")
        return None
    if len(args) != 3:
        logger.error("Exactly 3 args expected for sem_ver operator.")
        return None

    arg1, op, arg2 = args

    try:
        v1 = semver.Version.parse(str(arg1))
        v2 = semver.Version.parse(str(arg2))
    except ValueError as e:
        logger.exception(e)
        return None

    if op == "=":
        return v1 == v2
    elif op == "!=":
        return v1 != v2
    elif op == "<":
        return v1 < v2
    elif op == "<=":
        return v1 <= v2
    elif op == ">":
        return v1 > v2
    elif op == ">=":
        return v1 >= v2
    elif op == "^":
        return v1.major == v2.major
    elif op == "~":
        return v1.major == v2.major and v1.minor == v2.minor
    else:
        logger.error(f"Op not supported by sem_ver: {op}")
        return None
