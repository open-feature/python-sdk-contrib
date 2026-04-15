import json
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

T = typing.TypeVar("T")

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

    def set_flags(self, flag_configuration_json: str) -> None:
        with self._lock:
            data = json.loads(flag_configuration_json)
            self._flag_store.update(data)

    def set_flags_and_get_changed_keys(self, flag_configuration_json: str) -> list[str]:
        with self._lock:
            data = json.loads(flag_configuration_json)
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
                variant = targeting(flag.key, flag.targeting, evaluation_context)
                if variant is None:
                    result = _default_resolve(
                        flag, default_value, metadata, Reason.DEFAULT
                    )
                    self._check_type(result, flag_type)
                    return result

                if isinstance(variant, bool):
                    variant = str(variant).lower()
                elif not isinstance(variant, str):
                    variant = str(variant)

                if variant not in flag.variants:
                    raise GeneralError(
                        f"Resolved variant {variant} not in variants config."
                    )

            except ReferenceError:
                raise ParseError(f"Invalid targeting {targeting}") from ReferenceError

            variant, value = flag.get_variant(variant)
            if value is None:
                raise GeneralError(
                    f"Resolved variant {variant} not in variants config."
                )

            result = FlagResolutionDetails(
                value,
                variant=variant,
                reason=Reason.TARGETING_MATCH,
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
        # Skip type check when value is the caller's default (no variant resolved)
        # This happens for DEFAULT reason with no variant, or DISABLED flags
        if result.reason == Reason.DISABLED:
            return
        if result.reason == Reason.DEFAULT and result.variant is None:
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
