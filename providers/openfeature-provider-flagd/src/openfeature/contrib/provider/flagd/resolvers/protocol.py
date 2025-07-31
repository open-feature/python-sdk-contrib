import typing

from typing_extensions import Protocol

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType


class AbstractResolver(Protocol):
    def initialize(self, evaluation_context: EvaluationContext) -> None: ...

    def shutdown(self) -> None: ...

    def resolve_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]: ...

    def resolve_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]: ...

    def resolve_float_details(
        self,
        key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]: ...

    def resolve_integer_details(
        self,
        key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]: ...

    def resolve_object_details(
        self,
        key: str,
        default_value: typing.Union[
            typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]
        ],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        typing.Union[typing.Sequence[FlagValueType], typing.Mapping[str, FlagValueType]]
    ]: ...
