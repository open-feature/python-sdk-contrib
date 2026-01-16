from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    from botocore.config import Config


@dataclass
class CacheConfig:
    """
    Cache configuration for AWS SSM Provider.

    Attributes:
        cache_type: Type of cache to use. Options:
            - "lru": LRU (Least Recently Used) cache with size-based eviction only
            - "ttl": TTL (Time-To-Live) cache with both time-based expiration AND size-based eviction
            (default: "lru")
        ttl: Time-to-live for cached items in seconds. Only used when cache_type="ttl".
            (default: 300 / 5 minutes)
        size: Maximum number of items in the cache (default: 1000)
    """

    cache_type: Literal["lru", "ttl"] = "lru"
    ttl: int = 300  # 5 minutes in seconds
    size: int = 1000

    def __post_init__(self) -> None:
        """Validate cache_type value."""
        if self.cache_type not in ("lru", "ttl"):
            msg = f"cache_type must be 'lru' or 'ttl', got {self.cache_type!r}"
            raise ValueError(msg)


@dataclass
class AwsSsmProviderConfig:
    """
    Configuration for the AWS SSM Provider.

    Attributes:
        config: boto3 Config object (includes region_name, retries, timeouts, etc.)
        endpoint_url: Custom endpoint URL for SSM (optional, for testing with LocalStack/moto)
        enable_decryption: Whether to decrypt SecureString parameters (default: False)
        cache_config: Configuration for the local cache. Set to None to disable caching entirely.
            (default: CacheConfig() with cache_type="lru")

    Example:
        from botocore.config import Config

        provider_config = AwsSsmProviderConfig(
            config=Config(
                region_name="us-west-2",
                retries={"max_attempts": 10, "mode": "standard"},
                connect_timeout=5,
                read_timeout=60,
            ),
            enable_decryption=True,
            cache_config=CacheConfig(cache_type="ttl", ttl=60, size=500),
        )

        # Or disable caching entirely
        provider_config_no_cache = AwsSsmProviderConfig(
            config=Config(region_name="us-west-2"),
            cache_config=None,  # Disable caching
        )
    """

    config: Optional["Config"] = None
    endpoint_url: Optional[str] = None
    enable_decryption: bool = False
    cache_config: Optional[CacheConfig] = field(default_factory=CacheConfig)
