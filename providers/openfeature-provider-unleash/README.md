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

# Initialize the provider (required before use)
provider.initialize()

api.set_provider(provider)
```

### Configuration options

- `url`: The URL of your Unleash server
- `app_name`: The name of your application
- `api_token`: The API token for authentication

### Event handling

The Unleash provider supports OpenFeature events for monitoring provider state changes:

```python
from openfeature.event import ProviderEvent

def on_provider_ready(event_details):
    print(f"Provider {event_details['provider_name']} is ready")

def on_provider_error(event_details):
    print(f"Provider error: {event_details['error_message']}")

def on_configuration_changed(event_details):
    print(f"Configuration changed, flags: {event_details.get('flag_keys', [])}")

# Add event handlers
provider.add_handler(ProviderEvent.PROVIDER_READY, on_provider_ready)
provider.add_handler(ProviderEvent.PROVIDER_ERROR, on_provider_error)
provider.add_handler(ProviderEvent.PROVIDER_CONFIGURATION_CHANGED, on_configuration_changed)

# Remove event handlers
provider.remove_handler(ProviderEvent.PROVIDER_READY, on_provider_ready)
```

**Supported events:**
- `ProviderEvent.PROVIDER_READY`: Emitted when the provider is ready to evaluate flags
- `ProviderEvent.PROVIDER_ERROR`: Emitted when the provider encounters an error
- `ProviderEvent.PROVIDER_CONFIGURATION_CHANGED`: Emitted when flag configurations are updated
- `ProviderEvent.PROVIDER_STALE`: Emitted when the provider's cached state is no longer valid

### Example usage

```python
from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider

# Initialize the provider
provider = UnleashProvider(
    url="https://your-unleash-instance.com",
    app_name="my-python-app",
    api_token="my-token"
)
provider.initialize()
api.set_provider(provider)

# Get a client and evaluate flags
client = api.get_client()

# Boolean flag evaluation
is_enabled = client.get_boolean_value("my-feature", False)
print(f"Feature is enabled: {is_enabled}")

# String flag evaluation with context
context = {"userId": "user123", "sessionId": "session456"}
variant = client.get_string_value("my-variant-flag", "default", context)
print(f"Variant: {variant}")

# Shutdown when done
provider.shutdown()
```

## Development

### Running tests

```bash
pytest
```

### Type checking

```bash
mypy src/
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
