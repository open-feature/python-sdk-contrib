import json
import logging
import threading
import typing
from collections.abc import Mapping, Sequence

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason

from .model.flag import Flag
from .model.flag_store import FlagStore
from .targeting import targeting
from .targeting.custom_ops import ResolveResult

T = typing.TypeVar("T")

logger = logging.getLogger("openfeature.contrib")

# flag set metadata keys a resolve rule can't override; the schema only catches literal keys
RESERVED_METADATA_KEYS = frozenset({"flagSetId", "version"})
# reasons flagd sets itself; a resolve rule returning one keeps TARGETING_MATCH
RESERVED_REASONS = frozenset(
    {"ERROR", "DISABLED", "DEFAULT", "FALLBACK", "STATIC", "UNKNOWN", "CACHED", "STALE"}
)

# Type map for each resolve method
_TYPE_MAP: dict[str, tuple[type | tuple[type, ...], str]] = {
    "boolean": ((bool,), "bool"),
    "string": ((str,), "str"),
    "integer": ((int,), "int"),
    "float": ((int, float), "float"),
    "object": ((dict, list), "dict or list"),
}


def _merge_metadata(
    flag_metadata: Mapping[str, float | int | str | bool] | None,
    flag_set_metadata: Mapping[str, float | int | str | bool] | None,
) -> Mapping[str, float | int | str | bool]:
    metadata = {} if flag_set_metadata is None else dict(flag_set_metadata)
    if flag_metadata is not None:
        for key, value in flag_metadata.items():
            metadata[key] = value
    return metadata


def _merge_rule_metadata(
    metadata: Mapping[str, float | int | str | bool],
    rule_metadata: Mapping[str, float | int | str | bool],
) -> Mapping[str, float | int | str | bool]:
    merged = dict(metadata)
    for key, value in rule_metadata.items():
        if key in RESERVED_METADATA_KEYS:
            logger.debug(f"Ignoring reserved resolve metadata key {key}")
            continue
        merged[key] = value
    return merged


def _targeting_match(
    resolved: typing.Any, metadata: Mapping[str, float | int | str | bool]
) -> tuple[str, str, Mapping[str, float | int | str | bool]]:
    """Variant, reason and metadata of a non-null targeting result."""
    if isinstance(resolved, ResolveResult):
        reason = resolved.reason
        if reason in RESERVED_REASONS:
            logger.debug(f"Ignoring reserved resolve reason {reason}")
            reason = None
        if reason is None:
            reason = Reason.TARGETING_MATCH
        return (
            resolved.variant,
            reason,
            _merge_rule_metadata(metadata, resolved.metadata),
        )
    # convert to string to support shorthand
    if isinstance(resolved, bool):
        return str(resolved).lower(), Reason.TARGETING_MATCH, metadata
    return str(resolved), Reason.TARGETING_MATCH, metadata


def _default_resolve(
    flag: Flag,
    default_value: T,
    metadata: Mapping[str, float | int | str | bool],
    reason: Reason,
) -> FlagResolutionDetails:
    variant, value = flag.default
    if variant is None:
        return FlagResolutionDetails(
            default_value,
            variant=variant,
            reason=Reason.DEFAULT,
            flag_metadata=metadata,
        )
    if variant not in flag.variants:
        raise GeneralError(f"Resolved variant {variant} not in variants config.")
    return FlagResolutionDetails(
        value, variant=variant, flag_metadata=metadata, reason=reason
    )


class FlagdCore:
    """Reference implementation of the Evaluator protocol for flagd."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._flag_store = FlagStore()

    def set_flags(self, flag_configuration: str | dict[str, typing.Any]) -> None:
        with self._lock:
            data: dict[str, typing.Any] = (
                json.loads(flag_configuration)
                if isinstance(flag_configuration, str)
                else flag_configuration
            )
            self._flag_store.update(data)

    def set_flags_and_get_changed_keys(
        self, flag_configuration: str | dict[str, typing.Any]
    ) -> list[str]:
        with self._lock:
            data: dict[str, typing.Any] = (
                json.loads(flag_configuration)
                if isinstance(flag_configuration, str)
                else flag_configuration
            )
            return self._flag_store.update(data)

    def get_flag_set_metadata(self) -> Mapping[str, float | int | str | bool]:
        with self._lock:
            return dict(self._flag_store.flag_set_metadata)

    def resolve_boolean_value(
        self, flag_key: str, default_value: bool, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(flag_key, default_value, ctx, "boolean")

    def resolve_string_value(
        self, flag_key: str, default_value: str, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[str]:
        return self._resolve(flag_key, default_value, ctx, "string")

    def resolve_integer_value(
        self, flag_key: str, default_value: int, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[int]:
        return self._resolve(flag_key, default_value, ctx, "integer")

    def resolve_float_value(
        self, flag_key: str, default_value: float, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[float]:
        result = self._resolve(flag_key, default_value, ctx, "float")
        if isinstance(result.value, int):
            result.value = float(result.value)
        return result

    def resolve_object_value(
        self,
        flag_key: str,
        default_value: Sequence[FlagValueType] | Mapping[str, FlagValueType],
        ctx: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[Sequence[FlagValueType] | Mapping[str, FlagValueType]]:
        return self._resolve(flag_key, default_value, ctx, "object")

    def _resolve(
        self,
        key: str,
        default_value: T,
        evaluation_context: EvaluationContext | None = None,
        flag_type: str | None = None,
    ) -> FlagResolutionDetails[T]:
        with self._lock:
            flag = self._flag_store.get_flag(key)
            if not flag:
                raise FlagNotFoundError(
                    f"Flag with key {key} not present in flag store."
                )

            metadata = _merge_metadata(
                flag.metadata, self._flag_store.flag_set_metadata
            )

            if flag.state == "DISABLED":
                return FlagResolutionDetails(
                    default_value, flag_metadata=metadata, reason=Reason.DISABLED
                )

            if not flag.targeting:
                result = _default_resolve(flag, default_value, metadata, Reason.STATIC)
                self._check_type(result, flag_type)
                return result

            try:
                resolved = targeting(flag.key, flag.targeting, evaluation_context)
            except ReferenceError as e:
                raise ParseError(f"Invalid targeting {flag.targeting}") from e

            if resolved is None:
                result = _default_resolve(flag, default_value, metadata, Reason.DEFAULT)
                self._check_type(result, flag_type)
                return result

            variant, reason, metadata = _targeting_match(resolved, metadata)
            if variant not in flag.variants:
                raise GeneralError(
                    f"Resolved variant {variant} not in variants config."
                )

            variant, value = flag.get_variant(variant)
            if value is None:
                raise GeneralError(
                    f"Resolved variant {variant} not in variants config."
                )

            result = FlagResolutionDetails(
                value,
                variant=variant,
                reason=reason,
                flag_metadata=metadata,
            )
            self._check_type(result, flag_type)
            return result

    @staticmethod
    def _check_type(
        result: FlagResolutionDetails,
        flag_type: str | None,
    ) -> None:
        """Validate the resolved value type matches the expected flag type."""
        if flag_type is None:
            return
        # Skip type check when value is the caller's default (no variant resolved).
        # Not by reason: a resolve rule may return any reason, DISABLED included.
        if result.variant is None:
            return

        type_info = _TYPE_MAP.get(flag_type)
        if type_info is None:
            return

        expected_types, type_name = type_info
        value = result.value

        # For boolean type, reject int (since bool is subclass of int in Python)
        if (
            flag_type == "boolean"
            and isinstance(value, int)
            and not isinstance(value, bool)
        ):
            raise TypeMismatchError(
                f"Expected type {type_name} but got {type(value).__name__}"
            )

        # For integer type, reject bool (since bool is subclass of int)
        if flag_type == "integer" and isinstance(value, bool):
            raise TypeMismatchError(
                f"Expected type {type_name} but got {type(value).__name__}"
            )

        if not isinstance(value, expected_types):
            raise TypeMismatchError(
                f"Expected type {type_name} but got {type(value).__name__}"
            )
