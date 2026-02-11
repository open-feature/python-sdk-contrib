from collections.abc import Mapping, Sequence
from typing import Any, Callable, Optional, TypeVar, Union, cast

from cachebox import BaseCacheImpl, LRUCache, TTLCache

from openfeature.evaluation_context import EvaluationContext
from openfeature.flag_evaluation import FlagResolutionDetails, FlagValueType, Reason
from openfeature.provider import AbstractProvider, Metadata

from .config import AwsSsmProviderConfig
from .parsers import parse_boolean, parse_float, parse_integer, parse_object
from .ssm_service import SsmService

T = TypeVar("T")


class AwsSsmProvider(AbstractProvider):
    """Provider for AWS Systems Manager Parameter Store."""

    def __init__(self, config: Optional[AwsSsmProviderConfig] = None) -> None:
        """
        Initialize the AWS SSM Provider.

        Args:
            config: Configuration for the provider
        """
        self.config = config or AwsSsmProviderConfig()
        self.ssm_service = SsmService(
            config=self.config.config,
            endpoint_url=self.config.endpoint_url,
            enable_decryption=self.config.enable_decryption,
        )

        self.cache: Optional[BaseCacheImpl] = None
        if self.config.cache_config:
            cache_config = self.config.cache_config
            if cache_config.cache_type == "lru":
                self.cache = LRUCache(maxsize=cache_config.size)
            elif cache_config.cache_type == "ttl":
                self.cache = TTLCache(maxsize=cache_config.size, ttl=cache_config.ttl)

    def get_metadata(self) -> Metadata:
        """
        Get provider metadata.

        Returns:
            Provider metadata with name 'aws-ssm'
        """
        return Metadata(name="aws-ssm")

    def _get_cached_value(self, flag_key: str) -> Optional[Any]:
        """
        Get value from cache if available.

        Args:
            flag_key: The flag key

        Returns:
            The cached value or None if not cached
        """
        if self.cache is not None and flag_key in self.cache:
            return self.cache[flag_key]
        return None

    def _set_cache_value(self, flag_key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            flag_key: The flag key
            value: The value to cache
        """
        if self.cache is not None:
            self.cache[flag_key] = value

    def _resolve_with_cache(
        self,
        flag_key: str,
        parser: Optional[Callable[[str], T]] = None,
    ) -> FlagResolutionDetails[T]:
        """
        Base resolution logic with caching for synchronous operations.

        Args:
            flag_key: The flag key
            parser: Optional function to parse raw string value to desired type.
                   If None, returns the raw value unchanged.

        Returns:
            Flag resolution details with the parsed value
        """
        cached = self._get_cached_value(flag_key)
        if cached is not None:
            return FlagResolutionDetails(
                value=cached,
                reason=Reason.CACHED,
            )

        raw_value = self.ssm_service.get_parameter_value(flag_key)
        value = cast(T, parser(raw_value) if parser is not None else raw_value)

        self._set_cache_value(flag_key, value)
        return FlagResolutionDetails(
            value=value,
            reason=Reason.STATIC,
        )

    async def _resolve_with_cache_async(
        self,
        flag_key: str,
        parser: Optional[Callable[[str], T]] = None,
    ) -> FlagResolutionDetails[T]:
        """
        Base resolution logic with caching for asynchronous operations.

        Args:
            flag_key: The flag key
            parser: Optional function to parse raw string value to desired type.
                   If None, returns the raw value unchanged.

        Returns:
            Flag resolution details with the parsed value
        """
        cached = self._get_cached_value(flag_key)
        if cached is not None:
            return FlagResolutionDetails(
                value=cached,
                reason=Reason.CACHED,
            )

        raw_value = await self.ssm_service.get_parameter_value_async(flag_key)
        value = cast(T, parser(raw_value) if parser is not None else raw_value)

        self._set_cache_value(flag_key, value)
        return FlagResolutionDetails(
            value=value,
            reason=Reason.STATIC,
        )

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """
        Resolve a boolean flag.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the boolean value
        """
        return self._resolve_with_cache(flag_key, parse_boolean)

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """
        Resolve a string flag.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the string value
        """
        return self._resolve_with_cache(flag_key)

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """
        Resolve an integer flag.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the integer value
        """
        return self._resolve_with_cache(flag_key, parse_integer)

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """
        Resolve a float flag.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the float value
        """
        return self._resolve_with_cache(flag_key, parse_float)

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        """
        Resolve an object flag.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the object value
        """
        return self._resolve_with_cache(flag_key, parse_object)

    # Async methods
    async def resolve_boolean_details_async(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        """
        Resolve a boolean flag asynchronously.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the boolean value
        """
        return await self._resolve_with_cache_async(flag_key, parse_boolean)

    async def resolve_string_details_async(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        """
        Resolve a string flag asynchronously.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the string value
        """
        return await self._resolve_with_cache_async(flag_key)

    async def resolve_integer_details_async(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        """
        Resolve an integer flag asynchronously.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the integer value
        """
        return await self._resolve_with_cache_async(flag_key, parse_integer)

    async def resolve_float_details_async(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        """
        Resolve a float flag asynchronously.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the float value
        """
        return await self._resolve_with_cache_async(flag_key, parse_float)

    async def resolve_object_details_async(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        """
        Resolve an object flag asynchronously.

        Args:
            flag_key: The flag key
            default_value: The default value
            evaluation_context: The evaluation context (unused)

        Returns:
            Flag resolution details with the object value
        """
        return await self._resolve_with_cache_async(flag_key, parse_object)
