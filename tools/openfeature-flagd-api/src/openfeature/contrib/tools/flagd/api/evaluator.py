import typing
from collections.abc import Mapping, Sequence

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType


class Evaluator(typing.Protocol):
    def set_flags(self, flag_configuration_json: str) -> None: ...

    def set_flags_and_get_changed_keys(
        self, flag_configuration_json: str
    ) -> list[str]: ...

    def get_flag_set_metadata(self) -> Mapping[str, float | int | str | bool]: ...

    def resolve_boolean_value(
        self, flag_key: str, default_value: bool, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[bool]: ...

    def resolve_string_value(
        self, flag_key: str, default_value: str, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[str]: ...

    def resolve_integer_value(
        self, flag_key: str, default_value: int, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[int]: ...

    def resolve_float_value(
        self, flag_key: str, default_value: float, ctx: EvaluationContext | None = None
    ) -> FlagResolutionDetails[float]: ...

    def resolve_object_value(
        self,
        flag_key: str,
        default_value: Sequence[FlagValueType] | Mapping[str, FlagValueType],
        ctx: EvaluationContext | None = None,
    ) -> FlagResolutionDetails[
        Sequence[FlagValueType] | Mapping[str, FlagValueType]
    ]: ...
