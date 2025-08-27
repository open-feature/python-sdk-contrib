import json
from typing import Any, Callable, List, Mapping, Optional, Sequence, Union

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata
from openfeature.exception import (
    ErrorCode,
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
    TypeMismatchError,
)
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

    def _build_unleash_context(
        self, evaluation_context: Optional[EvaluationContext] = None
    ) -> Optional[dict[str, Any]]:
        """Convert OpenFeature evaluation context to Unleash context."""
        if not evaluation_context:
            return None

        context: dict[str, Any] = {}
        if evaluation_context.targeting_key:
            context["userId"] = evaluation_context.targeting_key
        context.update(evaluation_context.attributes)
        return context

    def _resolve_variant_flag(
        self,
        flag_key: str,
        default_value: Any,
        value_converter: Callable[[Any], Any],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Any]:
        """Helper method to resolve variant-based flags.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            value_converter: Function to convert payload value to desired type
            evaluation_context: Optional evaluation context (ignored for now)

        Returns:
            FlagResolutionDetails with the resolved value
        """
        try:
            # Use get_variant to get the variant payload
            context = self._build_unleash_context(evaluation_context)
            variant = self.client.get_variant(flag_key, context=context)

            # Check if the feature is enabled and has a payload
            if variant.get("enabled", False) and "payload" in variant:
                try:
                    payload_value = variant["payload"].get("value", default_value)
                    value = value_converter(payload_value)
                    return FlagResolutionDetails(
                        value=value,
                        reason=(
                            Reason.TARGETING_MATCH
                            if value != default_value
                            else Reason.DEFAULT
                        ),
                        variant=variant.get("name"),
                        error_code=None,
                        error_message=None,
                        flag_metadata={},
                    )
                except (ValueError, TypeError) as e:
                    # If payload value can't be converted, return error
                    return FlagResolutionDetails(
                        value=default_value,
                        reason=Reason.ERROR,
                        variant=variant.get("name"),
                        error_code=ErrorCode.TYPE_MISMATCH,
                        error_message=str(e),
                        flag_metadata={},
                    )
            else:
                return FlagResolutionDetails(
                    value=default_value,
                    reason=Reason.DEFAULT,
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

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details."""
        try:

            def fallback_func() -> bool:
                return default_value

            context = self._build_unleash_context(evaluation_context)
            value = self.client.is_enabled(
                flag_key, context=context, fallback_function=fallback_func
            )
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
        return self._resolve_variant_flag(
            flag_key, default_value, lambda payload_value: payload_value
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details."""
        return self._resolve_variant_flag(
            flag_key, default_value, lambda payload_value: int(payload_value)
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details."""
        return self._resolve_variant_flag(
            flag_key, default_value, lambda payload_value: float(payload_value)
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        """Resolve object flag details."""

        def object_converter(payload_value: Any) -> Union[dict, list]:
            # If payload is a string, try to parse it as JSON
            if isinstance(payload_value, str):
                value = json.loads(payload_value)
            else:
                value = payload_value

            # Ensure the value is a valid object (dict or list)
            if isinstance(value, (dict, list)):
                return value
            else:
                raise ValueError("Payload value is not a valid object")

        return self._resolve_variant_flag(flag_key, default_value, object_converter)

    async def resolve_boolean_details_async(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details asynchronously."""
        try:

            def fallback_func() -> bool:
                return default_value

            context = self._build_unleash_context(evaluation_context)
            value = self.client.is_enabled(
                flag_key, context=context, fallback_function=fallback_func
            )
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

    async def resolve_string_details_async(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve string flag details asynchronously."""
        return self._resolve_variant_flag(
            flag_key,
            default_value,
            lambda payload_value: payload_value,
            evaluation_context,
        )

    async def resolve_integer_details_async(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details asynchronously."""
        return self._resolve_variant_flag(
            flag_key,
            default_value,
            lambda payload_value: int(payload_value),
            evaluation_context,
        )

    async def resolve_float_details_async(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details asynchronously."""
        return self._resolve_variant_flag(
            flag_key,
            default_value,
            lambda payload_value: float(payload_value),
            evaluation_context,
        )

    async def resolve_object_details_async(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        """Resolve object flag details asynchronously."""

        def object_converter(payload_value: Any) -> Union[dict, list]:
            if isinstance(payload_value, str):
                value = json.loads(payload_value)
            else:
                value = payload_value

            if isinstance(value, (dict, list)):
                return value
            else:
                raise ValueError("Payload value is not a valid object")

        return self._resolve_variant_flag(
            flag_key, default_value, object_converter, evaluation_context
        )
