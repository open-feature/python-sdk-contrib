"""Flag evaluation functionality for Unleash provider."""

import json
from typing import Any, Callable, Optional, Protocol

from UnleashClient import UnleashClient

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason


class UnleashProvider(Protocol):
    """Protocol defining the interface needed by FlagEvaluator."""

    @property
    def client(self) -> UnleashClient: ...

    @property
    def app_name(self) -> str: ...

    def _build_unleash_context(
        self, evaluation_context: Optional[EvaluationContext] = None
    ) -> Optional[dict[str, Any]]: ...


class FlagEvaluator:
    """Manages flag evaluation functionality for the Unleash provider."""

    def __init__(self, provider: UnleashProvider) -> None:
        """Initialize the FlagEvaluator.

        Args:
            provider: The parent UnleashProvider instance
        """
        self._provider = provider

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """Resolve boolean flag details.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved boolean value
        """

        context = self._provider._build_unleash_context(evaluation_context)
        is_enabled = self._provider.client.is_enabled(
            flag_key,
            context=context,
            fallback_function=self._fallback_function(default_value),
        )

        return FlagResolutionDetails(
            value=is_enabled,
            reason=Reason.TARGETING_MATCH if is_enabled else Reason.DEFAULT,
            variant=None,
            error_code=None,
            error_message=None,
            flag_metadata={
                "source": "unleash",
                "enabled": is_enabled,
                "app_name": self._provider.app_name,
            },
        )

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """Resolve string flag details.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved string value
        """
        return self._resolve_variant_flag(
            flag_key, default_value, str, evaluation_context
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """Resolve integer flag details.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved integer value
        """
        return self._resolve_variant_flag(
            flag_key, default_value, int, evaluation_context
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """Resolve float flag details.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved float value
        """
        return self._resolve_variant_flag(
            flag_key, default_value, float, evaluation_context
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Any,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Any]:
        """Resolve object flag details.

        Args:
            flag_key: The flag key to resolve
            default_value: The default value to return if flag is disabled
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved object value
        """
        return self._resolve_variant_flag(
            flag_key, default_value, self._parse_json, evaluation_context
        )

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
            evaluation_context: Optional evaluation context

        Returns:
            FlagResolutionDetails with the resolved value
        """
        context = self._provider._build_unleash_context(evaluation_context)
        variant = self._provider.client.get_variant(flag_key, context=context)

        if variant.get("enabled", False) and "payload" in variant:
            try:
                payload_value = variant["payload"].get("value", default_value)
                value = value_converter(payload_value)
                return FlagResolutionDetails(
                    value=value,
                    reason=Reason.TARGETING_MATCH,
                    variant=variant.get("name"),
                    error_code=None,
                    error_message=None,
                    flag_metadata={
                        "source": "unleash",
                        "enabled": variant.get("enabled", False),
                        "variant_name": variant.get("name") or "",
                        "app_name": self._provider.app_name,
                    },
                )
            except ValueError as e:
                raise TypeMismatchError(str(e)) from e
            except ParseError:
                raise
        else:
            return FlagResolutionDetails(
                value=default_value,
                reason=Reason.DEFAULT,
                variant=None,
                error_code=None,
                error_message=None,
                flag_metadata={
                    "source": "unleash",
                    "enabled": variant.get("enabled", False),
                    "app_name": self._provider.app_name,
                },
            )

    def _parse_json(self, value: Any) -> Any:
        """Parse JSON value for object flags.

        Args:
            value: The value to parse

        Returns:
            Parsed JSON value

        Raises:
            ParseError: If JSON parsing fails
        """
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ParseError(f"Invalid JSON: {e}") from e
        return value

    def _fallback_function(self, default_value: bool) -> Callable:
        """Default fallback function for Unleash provider."""

        def fallback_function(feature_name: str, context: dict) -> bool:
            return default_value

        return fallback_function
