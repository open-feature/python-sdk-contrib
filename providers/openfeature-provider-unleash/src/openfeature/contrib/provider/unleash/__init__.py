from typing import List, Optional, Union

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata

__all__ = ["UnleashProvider"]


class UnleashProvider(AbstractProvider):
    def __init__(self):
        """Initialize the Unleash provider."""
        pass

    def get_metadata(self) -> Metadata:
        """Get provider metadata."""
        raise NotImplementedError("UnleashProvider.get_metadata() not implemented")

    def get_provider_hooks(self) -> List[Hook]:
        """Get provider hooks."""
        return []

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_boolean_details() not implemented"
        )

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve string flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_string_details() not implemented"
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_integer_details() not implemented"
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_float_details() not implemented"
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        """Resolve object flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_object_details() not implemented"
        )
