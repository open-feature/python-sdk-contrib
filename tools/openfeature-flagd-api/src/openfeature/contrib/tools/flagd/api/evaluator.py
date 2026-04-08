import typing

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType


class Evaluator(typing.Protocol):
    def set_flags(self, flag_configuration_json: str) -> None: ...

    def set_flags_and_get_changed_keys(self, flag_configuration_json: str) -> typing.List[str]: ...

    def get_flag_set_metadata(self) -> typing.Mapping[str, typing.Union[float, int, str, bool]]: ...

    def resolve_boolean_value(
        self, flag_key: str, default_value: bool, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[bool]: ...

    def resolve_string_value(
        self, flag_key: str, default_value: str, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[str]: ...

    def resolve_integer_value(
        self, flag_key: str, default_value: int, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[int]: ...

    def resolve_float_value(
        self, flag_key: str, default_value: float, ctx: typing.Optional[EvaluationContext] = None
    ) -> FlagResolutionDetails[float]: ...

    def resolve_object_value(
        self,
        flag_key: str,
        default_value: typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]],
        ctx: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]]]: ...
