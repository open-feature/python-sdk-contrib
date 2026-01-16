import time
from unittest.mock import AsyncMock, Mock

import pytest
from botocore.config import Config

from openfeature.contrib.provider.awsssm import (
    AwsSsmProvider,
    AwsSsmProviderConfig,
    CacheConfig,
)
from openfeature.exception import FlagNotFoundError, ParseError, TypeMismatchError
from openfeature.flag_evaluation import Reason


def test_provider_metadata():
    provider = AwsSsmProvider()
    metadata = provider.get_metadata()
    assert metadata is not None
    assert metadata.name == "aws-ssm"


def test_parameter_not_found_raises_error():
    provider = AwsSsmProvider()
    provider.ssm_service.get_parameter_value = Mock(
        side_effect=FlagNotFoundError("Parameter not found")
    )

    with pytest.raises(FlagNotFoundError):
        provider.resolve_string_details("nonexistent-flag", "default", None)


@pytest.mark.parametrize(
    ("resolve_method", "ssm_value", "expected_value", "default_value"),
    [
        ("resolve_string_details", "hello-world", "hello-world", "default"),
        ("resolve_boolean_details", "true", True, False),
        ("resolve_boolean_details", "false", False, True),
        ("resolve_integer_details", "42", 42, 0),
        ("resolve_integer_details", "-123", -123, 0),
        ("resolve_float_details", "3.14", 3.14, 0.0),
        ("resolve_float_details", "-2.5", -2.5, 0.0),
        (
            "resolve_object_details",
            '{"key": "value", "number": 42}',
            {"key": "value", "number": 42},
            {},
        ),
        ("resolve_object_details", '[1, 2, 3, "four"]', [1, 2, 3, "four"], []),
    ],
)
def test_flag_resolution(resolve_method, ssm_value, expected_value, default_value):
    provider = AwsSsmProvider()
    provider.ssm_service.get_parameter_value = Mock(return_value=ssm_value)

    resolve_func = getattr(provider, resolve_method)
    result = resolve_func("test-flag", default_value, None)

    assert result.value == expected_value
    assert result.reason == Reason.STATIC


@pytest.mark.parametrize(
    ("resolve_method", "invalid_value", "default_value", "expected_exception"),
    [
        ("resolve_boolean_details", "yes", False, TypeMismatchError),
        ("resolve_integer_details", "not-a-number", 0, TypeMismatchError),
        ("resolve_float_details", "not-a-float", 0.0, TypeMismatchError),
        ("resolve_object_details", "not-valid-json", {}, ParseError),
        ("resolve_object_details", "42", {}, ParseError),
    ],
)
def test_invalid_flag_values(
    resolve_method, invalid_value, default_value, expected_exception
):
    provider = AwsSsmProvider()
    provider.ssm_service.get_parameter_value = Mock(return_value=invalid_value)

    resolve_func = getattr(provider, resolve_method)
    with pytest.raises(expected_exception):
        resolve_func("test-flag", default_value, None)


def test_cache_enabled_returns_cached_value():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="lru", size=100),
    )
    provider = AwsSsmProvider(config=config)

    # Mock to track call count
    call_count = [0]

    def mock_get(flag_key):
        call_count[0] += 1
        return "original"

    provider.ssm_service.get_parameter_value = mock_get

    # First call fetches from SSM
    result1 = provider.resolve_string_details("cached-flag", "default", None)
    assert result1.value == "original"
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Second call returns cached value
    result2 = provider.resolve_string_details("cached-flag", "default", None)
    assert result2.value == "original"
    assert result2.reason == Reason.CACHED
    assert call_count[0] == 1  # No new call to SSM


def test_cache_disabled_always_fetches():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=None,  # Disable caching
    )
    provider = AwsSsmProvider(config=config)

    # Mock to track call count and return different values
    call_count = [0]

    def mock_get(flag_key):
        call_count[0] += 1
        return f"value-{call_count[0]}"

    provider.ssm_service.get_parameter_value = mock_get

    # First call
    result1 = provider.resolve_string_details("uncached-flag", "default", None)
    assert result1.value == "value-1"
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Second call gets new value (no caching)
    result2 = provider.resolve_string_details("uncached-flag", "default", None)
    assert result2.value == "value-2"
    assert result2.reason == Reason.STATIC
    assert call_count[0] == 2


def test_different_flag_types_use_same_cache():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="lru", size=100),
    )
    provider = AwsSsmProvider(config=config)

    # Mock to return different values based on flag key
    def mock_get(flag_key):
        # Normalize flag keys (provider adds leading slash)
        if flag_key in ("/string-flag", "string-flag"):
            return "test"
        elif flag_key in ("/int-flag", "int-flag"):
            return "42"
        return "unknown"

    provider.ssm_service.get_parameter_value = mock_get

    # Cache string
    result1 = provider.resolve_string_details("string-flag", "default", None)
    assert result1.reason == Reason.STATIC

    # Cache int
    result2 = provider.resolve_integer_details("int-flag", 0, None)
    assert result2.reason == Reason.STATIC

    # Both should be cached
    result3 = provider.resolve_string_details("string-flag", "default", None)
    assert result3.reason == Reason.CACHED

    result4 = provider.resolve_integer_details("int-flag", 0, None)
    assert result4.reason == Reason.CACHED


def test_cache_type_lru_uses_lru_cache():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="lru", size=100),
    )
    provider = AwsSsmProvider(config=config)

    # Track calls
    call_count = [0]

    def mock_get(flag_key):
        call_count[0] += 1
        return "cached"

    provider.ssm_service.get_parameter_value = mock_get

    # First call caches the value
    result1 = provider.resolve_string_details("lru-flag", "default", None)
    assert result1.value == "cached"
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Second call returns cached value (LRU cache doesn't expire by time)
    result2 = provider.resolve_string_details("lru-flag", "default", None)
    assert result2.value == "cached"
    assert result2.reason == Reason.CACHED
    assert call_count[0] == 1  # No new call


def test_cache_type_ttl_expires_after_ttl():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="ttl", ttl=0.5, size=100),  # 0.5 second TTL
    )
    provider = AwsSsmProvider(config=config)

    # Create mock that tracks calls
    call_count = [0]

    def tracked_get(flag_key):
        call_count[0] += 1
        return f"value-{call_count[0]}"

    provider.ssm_service.get_parameter_value = tracked_get

    # First call - cache miss
    result1 = provider.resolve_string_details("ttl-flag", "default", None)
    assert result1.value == "value-1"
    assert result1.reason == Reason.STATIC
    first_call_count = call_count[0]

    # Immediate second call - cache hit
    result2 = provider.resolve_string_details("ttl-flag", "default", None)
    assert result2.value == "value-1"
    assert result2.reason == Reason.CACHED
    assert call_count[0] == first_call_count  # No new SSM call

    # Wait for TTL to expire
    time.sleep(0.6)

    # Third call after TTL - cache should expire, fetches new value
    result3 = provider.resolve_string_details("ttl-flag", "default", None)
    assert result3.value == "value-2"
    assert result3.reason == Reason.STATIC
    assert call_count[0] > first_call_count  # New SSM call was made


def test_cache_type_ttl_hit_before_expiration():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="ttl", ttl=10000, size=100),  # 10s TTL
    )
    provider = AwsSsmProvider(config=config)

    call_count = [0]

    def mock_get(flag_key):
        call_count[0] += 1
        return "cached"

    provider.ssm_service.get_parameter_value = mock_get

    # First call caches
    result1 = provider.resolve_string_details("ttl-flag-valid", "default", None)
    assert result1.value == "cached"
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Immediate second call returns cached value (TTL not expired)
    result2 = provider.resolve_string_details("ttl-flag-valid", "default", None)
    assert result2.value == "cached"
    assert result2.reason == Reason.CACHED
    assert call_count[0] == 1


def test_cache_config_none_disables_caching():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=None,  # Disable caching entirely
    )
    provider = AwsSsmProvider(config=config)

    call_count = [0]

    def mock_get(flag_key):
        call_count[0] += 1
        return f"value-{call_count[0]}"

    provider.ssm_service.get_parameter_value = mock_get

    # First call
    result1 = provider.resolve_string_details("no-cache", "default", None)
    assert result1.value == "value-1"
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Second call gets new value (no caching)
    result2 = provider.resolve_string_details("no-cache", "default", None)
    assert result2.value == "value-2"
    assert result2.reason == Reason.STATIC
    assert call_count[0] == 2


def test_cache_type_invalid_raises_error():
    with pytest.raises(ValueError, match="cache_type must be"):
        config = AwsSsmProviderConfig(
            config=Config(region_name="us-east-1"),
            cache_config=CacheConfig(cache_type="invalid", size=100),  # type: ignore[arg-type]
        )
        AwsSsmProvider(config=config)


def test_cache_config_validation_invalid_type():
    with pytest.raises(ValueError, match="cache_type must be"):
        CacheConfig(cache_type="invalid")  # type: ignore[arg-type]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolve_method", "ssm_value", "expected_value", "default_value"),
    [
        ("resolve_string_details_async", "async-value", "async-value", "default"),
        ("resolve_boolean_details_async", "true", True, False),
        ("resolve_integer_details_async", "99", 99, 0),
        ("resolve_float_details_async", "1.5", 1.5, 0.0),
        (
            "resolve_object_details_async",
            '{"async": true}',
            {"async": True},
            {},
        ),
    ],
)
async def test_async_flag_resolution(
    resolve_method, ssm_value, expected_value, default_value
):
    config = AwsSsmProviderConfig(config=Config(region_name="us-east-1"))
    provider = AwsSsmProvider(config=config)

    # Mock async method
    provider.ssm_service.get_parameter_value_async = AsyncMock(return_value=ssm_value)

    resolve_func = getattr(provider, resolve_method)
    result = await resolve_func("test-flag", default_value, None)

    assert result.value == expected_value
    assert result.reason == Reason.STATIC


@pytest.mark.asyncio
async def test_async_cache_hit():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="lru", size=100),
    )
    provider = AwsSsmProvider(config=config)

    call_count = [0]

    async def mock_get_async(flag_key):
        call_count[0] += 1
        return "test"

    provider.ssm_service.get_parameter_value_async = mock_get_async

    # First call caches
    result1 = await provider.resolve_string_details_async(
        "cached-async", "default", None
    )
    assert result1.reason == Reason.STATIC
    assert call_count[0] == 1

    # Second call from cache
    result2 = await provider.resolve_string_details_async(
        "cached-async", "default", None
    )
    assert result2.reason == Reason.CACHED
    assert call_count[0] == 1  # No new call
