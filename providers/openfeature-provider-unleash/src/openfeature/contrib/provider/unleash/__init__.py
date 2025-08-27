from typing import List, Mapping, Optional, Sequence, Union

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata
from openfeature.exception import ErrorCode
from UnleashClient import UnleashClient

__all__ = ["UnleashProvider"]


class UnleashProvider(AbstractProvider):
    def __init__(
        self,
        url: str,
        app_name: str,
        api_token: str,
    ) -> None:
        """Initialize the Unleash provider.

        Args:
            url: The Unleash API URL
            app_name: The application name
            api_token: The API token for authentication
        """
        self.client = UnleashClient(
            url=url, app_name=app_name, custom_headers={"Authorization": api_token}
        )
        self.client.initialize_client()

    def get_metadata(self) -> Metadata:
        """Get provider metadata."""
        return Metadata(name="Unleash Provider")

    def get_provider_hooks(self) -> List[Hook]:
        """Get provider hooks."""
        return []

    def shutdown(self) -> None:
        """Shutdown the Unleash client."""
        if hasattr(self, "client"):
            self.client.destroy()

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details."""
        try:
            # UnleashClient.is_enabled expects (feature_name, context=None, fallback_function=None)
            # We use a fallback function to return our default value
            def fallback_func() -> bool:
                return default_value

            value = self.client.is_enabled(flag_key, fallback_function=fallback_func)
            return FlagResolutionDetails(
                value=value,
                reason=(
                    Reason.TARGETING_MATCH if value != default_value else Reason.DEFAULT
                ),
                variant=None,
                error_code=None,
                error_message=None,
                flag_metadata={},
            )
        except Exception as e:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.ERROR,
                variant=None,
                error_code=ErrorCode.GENERAL,
                error_message=str(e),
                flag_metadata={},
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
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        """Resolve object flag details."""
        raise NotImplementedError(
            "UnleashProvider.resolve_object_details() not implemented"
        )
