import logging
import typing
from collections.abc import Sequence
from dataclasses import dataclass

import mmh3
import semver

MAX_WEIGHT_SUM = 2_147_483_647  # MaxInt32

JsonPrimitive: typing.TypeAlias = str | bool | float | int
JsonLogicArg: typing.TypeAlias = JsonPrimitive | Sequence[JsonPrimitive]

logger = logging.getLogger("openfeature.contrib")


@dataclass
class Fraction:
    variant: str | float | int | bool | None
    weight: int = 1


def _resolve_bucket_by(data: dict, args: tuple) -> tuple[str | None, tuple]:
    if isinstance(args[0], str):
        return args[0], args[1:]

    seed = data.get("$flagd", {}).get("flagKey", "")
    targeting_key = data.get("targetingKey")
    if not targeting_key:
        logger.error("No targetingKey provided for fractional shorthand syntax.")
        return None, args
    return seed + targeting_key, args


def fractional(data: dict, *args: JsonLogicArg) -> str | float | int | bool | None:
    if not args:
        logger.error("No arguments provided to fractional operator.")
        return None

    bucket_by, args = _resolve_bucket_by(data, args)

    if not bucket_by:
        logger.error("No hashKey value resolved")
        return None

    hash_value = mmh3.hash(bucket_by, signed=False)

    total_weight = 0
    fractions = []
    try:
        for arg in args:
            fraction = _parse_fraction(arg)
            fractions.append(fraction)
            total_weight += fraction.weight

    except ValueError:
        logger.debug(f"Invalid {args} configuration")
        return None

    if total_weight > MAX_WEIGHT_SUM:
        logger.error(f"Total fractional weight exceeds MaxInt32 ({MAX_WEIGHT_SUM:,}).")
        return None

    bucket = (hash_value * total_weight) >> 32

    range_end = 0
    for fraction in fractions:
        range_end += fraction.weight
        if bucket < range_end:
            return fraction.variant
    return None


def _parse_fraction(arg: JsonLogicArg) -> Fraction:
    if not isinstance(arg, (tuple, list)) or not arg or len(arg) > 2:
        raise ValueError(
            "Fractional variant weights must be (str, int) tuple or [str] list"
        )

    variant = arg[0]

    weight = None
    if len(arg) == 2:
        w = arg[1]
        if isinstance(w, bool):
            raise ValueError("Fractional weight value isn't of type 'int'")
        elif isinstance(w, int):
            weight = w
        else:
            raise ValueError("Fractional weight value isn't of type 'int'")

    fraction = Fraction(variant=variant)
    if weight is not None:
        fraction.weight = weight

    return fraction


def starts_with(data: dict, *args: JsonLogicArg) -> bool | None:
    def f(s1: str, s2: str) -> bool:
        return s1.startswith(s2)

    return string_comp(f, data, *args)


def ends_with(data: dict, *args: JsonLogicArg) -> bool | None:
    def f(s1: str, s2: str) -> bool:
        return s1.endswith(s2)

    return string_comp(f, data, *args)


def string_comp(
    comparator: typing.Callable[[str, str], bool], data: dict, *args: JsonLogicArg
) -> bool | None:
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


def sem_ver(data: dict, *args: JsonLogicArg) -> bool | None:  # noqa: C901
    if not args:
        logger.error("No arguments provided to sem_ver operator.")
        return None
    if len(args) != 3:
        logger.error("Exactly 3 args expected for sem_ver operator.")
        return None

    arg1, op, arg2 = args

    try:
        v1 = parse_version(arg1)
        v2 = parse_version(arg2)
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


def parse_version(arg: typing.Any) -> semver.Version:
    version = str(arg)
    if version.startswith(("v", "V")):
        version = version[1:]

    return semver.Version.parse(version)
