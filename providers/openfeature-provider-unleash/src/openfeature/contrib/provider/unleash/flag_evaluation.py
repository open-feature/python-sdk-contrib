"""Flag evaluation functionality for Unleash provider."""

from typing import Any, Callable, Optional, Protocol

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
import requests


class UnleashProvider(Protocol):
    """Protocol defining the interface needed by FlagEvaluator."""

    @property
    def client(self) -> Optional[Any]: ...

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
        if not self._provider.client:
            raise GeneralError("Provider not initialized. Call initialize() first.")

        try:
            context = self._provider._build_unleash_context(evaluation_context)
            is_enabled = self._provider.client.is_enabled(flag_key, context=context)

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
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise FlagNotFoundError(f"Flag not found: {flag_key}")
            raise GeneralError(f"HTTP error: {e}")
        except (FlagNotFoundError, TypeMismatchError, ParseError, GeneralError):
            # Re-raise specific OpenFeature exceptions
            raise
        except Exception as e:
            raise GeneralError(f"Unexpected error: {e}")

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
        if not self._provider.client:
            raise GeneralError("Provider not initialized. Call initialize() first.")

        try:
            # Use get_variant to get the variant payload
            context = self._provider._build_unleash_context(evaluation_context)
            variant = self._provider.client.get_variant(flag_key, context=context)

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
                        flag_metadata={
                            "source": "unleash",
                            "enabled": variant.get("enabled", False),
                            "variant_name": variant.get("name") or "",
                            "app_name": self._provider.app_name,
                        },
                    )
                except (ValueError, TypeError) as e:
                    # If payload value can't be converted, raise TypeMismatchError
                    raise TypeMismatchError(str(e))
                except ParseError:
                    # Re-raise ParseError directly
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
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                raise FlagNotFoundError(f"Flag not found: {flag_key}")
            raise GeneralError(f"HTTP error: {e}")
        except (FlagNotFoundError, TypeMismatchError, ParseError, GeneralError):
            # Re-raise specific OpenFeature exceptions
            raise
        except Exception as e:
            raise GeneralError(f"Unexpected error: {e}")

    def _parse_json(self, value: Any) -> Any:
        """Parse JSON value for object flags.

        Args:
            value: The value to parse

        Returns:
            Parsed JSON value

        Raises:
            ParseError: If JSON parsing fails
        """
        import json

        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as e:
                raise ParseError(f"Invalid JSON: {e}")
        return value
