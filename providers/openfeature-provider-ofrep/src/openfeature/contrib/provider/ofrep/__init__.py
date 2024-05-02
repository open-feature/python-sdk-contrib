from typing import List, Optional, Union

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata


class OFREPProvider(AbstractProvider):
    def get_metadata(self) -> Metadata:
        return Metadata(name="OpenFeature Remote Evaluation Protocol Provider")

    def get_provider_hooks(self) -> List[Hook]:
        return []

    def resolve_boolean_details(  # type: ignore[empty-body]
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]: ...

    def resolve_string_details(  # type: ignore[empty-body]
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]: ...

    def resolve_integer_details(  # type: ignore[empty-body]
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]: ...

    def resolve_float_details(  # type: ignore[empty-body]
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]: ...

    def resolve_object_details(  # type: ignore[empty-body]
        self,
        flag_key: str,
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]: ...
