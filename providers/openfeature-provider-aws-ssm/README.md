# OpenFeature AWS SSM Parameter Store Provider

This provider enables the use of [AWS Systems Manager (SSM) Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html) as a backend for [OpenFeature](https://openfeature.dev/) feature flags in Python.

## Installation

```bash
pip install openfeature-provider-aws-ssm
```

For async support:

```bash
pip install openfeature-provider-aws-ssm[async]
```

## Usage

### Basic Usage

```python
from openfeature import api
from openfeature.contrib.provider.awsssm import AwsSsmProvider

# Initialize the provider
provider = AwsSsmProvider()

# Set the provider
api.set_provider(provider)

# Get a client
client = api.get_client()

# Evaluate a flag
is_enabled = client.get_boolean_value("my-feature-flag", default_value=False)
```

### With Configuration

```python
from botocore.config import Config
from openfeature.contrib.provider.awsssm import (
    AwsSsmProvider,
    AwsSsmProviderConfig,
    CacheConfig,
)

config = AwsSsmProviderConfig(
    config=Config(
        region_name="us-west-2",
        retries={"max_attempts": 10, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    ),
    enable_decryption=True,  # For SecureString parameters
    cache_config=CacheConfig(
        cache_type="ttl",
        size=1000,
        ttl=300,  # 5 minutes in seconds
    ),
)

provider = AwsSsmProvider(config=config)
api.set_provider(provider)
```

### Async Usage

```python
from openfeature import api
from openfeature.contrib.provider.awsssm import AwsSsmProvider

provider = AwsSsmProvider()
api.set_provider(provider)

client = api.get_client()

# Async flag evaluation
is_enabled = await client.get_boolean_value_async(
    "my-feature-flag", default_value=False
)
```

## Flag Key Mapping

Flag keys are mapped to SSM parameter names with the following rules:

- If the flag key starts with `/`, it's used as-is
- Otherwise, a leading `/` is automatically prepended

Examples:

- Flag key `my-feature` → Parameter `/my-feature`
- Flag key `/app/prod/feature` → Parameter `/app/prod/feature`

## Flag Types

The provider supports all OpenFeature flag types:

| OpenFeature Type | SSM Parameter Value   | Parsing Rules                                                                 |
| ---------------- | --------------------- | ----------------------------------------------------------------------------- |
| **Boolean**      | `"true"` or `"false"` | Case-insensitive. Other values raise `TypeMismatchError`                      |
| **String**       | Any string            | Returned as-is                                                                |
| **Integer**      | `"42"`, `"-10"`       | Parsed with `int()`. Invalid values raise `TypeMismatchError`                 |
| **Float**        | `"3.14"`, `"-2.5"`    | Parsed with `float()`. Invalid values raise `TypeMismatchError`               |
| **Object**       | Valid JSON            | Parsed as JSON object or array. Invalid JSON or primitives raise `ParseError` |

## Configuration Options

### `AwsSsmProviderConfig`

| Parameter           | Type                     | Default         | Description                                                         |
| ------------------- | ------------------------ | --------------- | ------------------------------------------------------------------- |
| `config`            | `botocore.config.Config` | `None`          | boto3 Config object (includes region_name, retries, timeouts, etc.) |
| `endpoint_url`      | `str`                    | `None`          | Custom SSM endpoint URL (for testing with LocalStack/moto)          |
| `enable_decryption` | `bool`                   | `False`         | Whether to decrypt SecureString parameters                          |
| `cache_config`      | `CacheConfig`            | `CacheConfig()` | Configuration for the local cache                                   |

### `CacheConfig`

The provider supports multiple caching strategies to optimize performance. To disable caching entirely, pass `cache_config=None` when creating the provider config.

| Parameter    | Type                    | Default | Description                                                                  |
| ------------ | ----------------------- | ------- | ---------------------------------------------------------------------------- |
| `cache_type` | `Literal["lru", "ttl"]` | `"lru"` | Type of cache: `"lru"` (size-based) or `"ttl"` (time-based)                  |
| `ttl`        | `int`                   | `300`   | Time-to-live for cached items in seconds (only used with `cache_type="ttl"`) |
| `size`       | `int`                   | `1000`  | Maximum number of items in the cache                                         |

#### Cache Types

- **`"lru"` (default)**: Least Recently Used cache with size-based eviction only. Cached values persist until evicted due to size limits.
- **`"ttl"`**: Time-To-Live cache with both time-based expiration AND size-based eviction. Cached values automatically expire after the configured TTL, even if space remains in the cache.

#### Cache Examples

```python
# LRU cache (default) - size-based eviction only
cache_config=CacheConfig(cache_type="lru", size=500)

# TTL cache - expires after 60 seconds
cache_config=CacheConfig(cache_type="ttl", ttl=60, size=500)

# No caching - pass cache_config=None to the provider config
provider_config = AwsSsmProviderConfig(cache_config=None)
```

For more information on the `Config` object, see the [boto3 configuration documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html).

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
