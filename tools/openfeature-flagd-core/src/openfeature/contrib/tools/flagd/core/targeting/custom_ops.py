import logging
import math
import typing
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

import cbor2
import mmh3
import semver

MAX_WEIGHT_SUM = 2_147_483_647  # MaxInt32

JsonPrimitive: typing.TypeAlias = str | bool | float | int
JsonLogicArg: typing.TypeAlias = JsonPrimitive | Sequence[JsonPrimitive]

logger = logging.getLogger("openfeature.contrib")


@dataclass
class Fraction:
    variant: "str | float | int | bool | ResolveResult | None"
    weight: int = 1


@dataclass(frozen=True)
class ResolveResult:
    """Result of the terminal ``resolve`` operator.

    No JSON input decodes to this type, so evaluation context data can't forge one.
    """

    # None behaves like a plain null targeting result
    variant: str | None
    # None keeps the reason of the equivalent plain result
    reason: str | None = None
    # merged over flag set and flag metadata
    metadata: Mapping[str, str | bool | int | float] = field(default_factory=dict)


def _resolve_bucket_by(data: dict, args: tuple) -> tuple[typing.Any, tuple]:
    if not isinstance(args[0], (list, tuple)):
        return args[0], args[1:]

    targeting_key = data.get("targetingKey")
    if targeting_key is None or not isinstance(targeting_key, str) or not targeting_key:
        logger.error(
            "No valid string targetingKey provided for fractional shorthand syntax."
        )
        return None, args

    flag_key = data.get("$flagd", {}).get("flagKey", "")
    return [flag_key, targeting_key], args


def normalize_numbers(data: typing.Any) -> typing.Any:
    """
    Recursively convert floats that have no fractional part into integers,
    but only if they fit within the 64-bit signed or unsigned integer range [-2^63, 2^64 - 1].
    This ensures consistency for integer representations while avoiding converting massive
    floats into bignums, adhering to the flagd CBOR fractional specification.
    """
    if isinstance(data, dict):
        return {k: normalize_numbers(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [normalize_numbers(v) for v in data]
    elif (
        isinstance(data, float) and data.is_integer() and -(2**63) <= data <= 2**64 - 1
    ):
        return int(data)
    return data


def fractional(data: dict, *args: typing.Any) -> typing.Any:
    if not args:
        logger.error("No arguments provided to fractional operator.")
        return None

    bucket_by, args = _resolve_bucket_by(data, args)

    if bucket_by is None:
        logger.error("No hashKey value resolved")
        return None

    try:
        bucket_by = normalize_numbers(bucket_by)
        cbor_bytes = cbor2.dumps(bucket_by, canonical=True)
    except Exception as e:
        logger.error(f"Failed to encode bucket_by to CBOR: {e}")
        return None

    hash_value = mmh3.hash(cbor_bytes, signed=False)

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

    if total_weight <= 0:
        logger.error("Total fractional weight must be greater than 0.")
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
    # any other result (e.g. an object or array) makes fractional return None
    if variant is not None and not isinstance(
        variant, (str, int, float, bool, ResolveResult)
    ):
        raise ValueError("Fractional variant must be a primitive or a resolve result")

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
        # negative weights can be the result of rollout calculations, so we clamp to 0 rather than raising an error
        fraction.weight = max(0, weight)

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
    comparator: typing.Callable[[str, str], bool],
    data: dict,
    *args: JsonLogicArg,
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
        return None
    if not isinstance(arg2, str):
        logger.debug(f"incorrect argument for second argument, expected string: {arg2}")
        return None

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
        v1 = normalize_version(arg1)
        v2 = normalize_version(arg2)
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


def normalize_version(arg: typing.Any) -> semver.Version:
    version = str(arg)
    if version.startswith(("v", "V")):
        version = version[1:]

    # Pad partial versions (e.g. "1" → "1.0.0", "1.2" → "1.2.0")
    numeric_part = version.split("-")[0].split("+")[0]
    dot_count = numeric_part.count(".")
    if dot_count < 2:
        version = numeric_part + ".0" * (2 - dot_count) + version[len(numeric_part) :]

    return semver.Version.parse(version)


def resolve(data: dict, *args: typing.Any) -> ResolveResult | None:
    """Terminal ``resolve`` operator: ``["variant"|null, "reason"?, [["key", value], ...]?]``.

    Placement is enforced by the targeting schema. Malformed (computed) arguments return
    None like the other custom operators, so the flag falls back to its default variant.
    """
    if not 1 <= len(args) <= 3:
        logger.debug("resolve takes 1 to 3 arguments")
        return None

    variant = None
    if args[0] is not None:
        variant = _resolve_variant_key(args[0])
        if variant is None:
            logger.debug("resolve variant must be a string, boolean, or finite number")
            return None

    reason = args[1] if len(args) > 1 else None
    if reason is not None and not isinstance(reason, str):
        logger.debug("resolve reason must be a string or null")
        return None

    pairs = args[2] if len(args) > 2 else None
    metadata = {} if pairs is None else _resolve_metadata(pairs)
    if metadata is None:
        return None

    return ResolveResult(variant, reason, metadata)


def _resolve_variant_key(value: typing.Any) -> str | None:
    # coerce like a plain targeting result
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, str):
        return value
    if isinstance(value, int) or (isinstance(value, float) and math.isfinite(value)):
        return str(value)
    return None


def _resolve_metadata(
    pairs: typing.Any,
) -> dict[str, str | bool | int | float] | None:
    if not isinstance(pairs, (list, tuple)):
        logger.debug("resolve metadata must be an array of [key, value] pairs")
        return None
    metadata: dict[str, str | bool | int | float] = {}
    for pair in pairs:
        if (
            not isinstance(pair, (list, tuple))
            or len(pair) != 2
            or not isinstance(pair[0], str)
        ):
            logger.debug("resolve metadata pair must be a [string, value] array")
            return None
        key, value = pair
        # NaN and Infinity (e.g. a computed 1/0) can't be encoded as JSON
        valid_value = isinstance(value, (str, bool, int)) or (
            isinstance(value, float) and math.isfinite(value)
        )
        if not valid_value:
            logger.debug(
                "resolve metadata value must be a string, finite number, or boolean"
            )
            return None
        metadata[key] = value
    return metadata
