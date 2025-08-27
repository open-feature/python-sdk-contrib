# Unleash Provider for OpenFeature

This provider is designed to use [Unleash](https://unleash.io/).

## Installation

```
pip install openfeature-provider-unleash
```

## Configuration and Usage

Instantiate a new UnleashProvider instance and configure the OpenFeature SDK to use it:

```python
from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider

# Initialize the provider with your Unleash configuration
provider = UnleashProvider(
    url="https://your-unleash-instance.com",
    app_name="my-python-app",
    api_token="your-api-token"
)

api.set_provider(provider)
```

### Configuration options

- `url`: The URL of your Unleash server
- `app_name`: The name of your application
- `api_token`: The API token for authentication

### Example usage

```python
from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider

# Set up the provider
provider = UnleashProvider(
    url="https://unleash.example.com",
    app_name="my-app",
    api_token="my-token"
)
api.set_provider(provider)

# Get a client and evaluate flags
client = api.get_client()

# Resolve a boolean flag
flag_details = client.get_boolean_details("my-feature-flag", default_value=False)
if flag_details.value:
    print("Feature is enabled!")
else:
    print("Feature is disabled")

# Clean up when done
provider.shutdown()
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
