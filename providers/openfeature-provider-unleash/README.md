# Unleash Provider for OpenFeature

This provider is designed to use [Unleash](https://www.getunleash.io/).

## Installation

```
pip install openfeature-provider-unleash
```

### Requirements

- Python 3.9+
- `openfeature-sdk>=0.8.2`
- `UnleashClient>=6.3.0`

## Configuration and Usage

Instantiate a new UnleashProvider instance and configure the OpenFeature SDK to use it:

```python
from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider

# Initialize the provider with your Unleash configuration
provider = UnleashProvider(
    url="https://my-unleash-instance.com",
    app_name="my-python-app",
    api_token="my-api-token",
)

# Initialize the provider (required before use)
provider.initialize()

api.set_provider(provider)
```

### Configuration options

- `url`: The URL of your Unleash server
- `app_name`: The name of your application
- `api_token`: The API token for authentication

### Evaluation context mapping

When evaluating flags, the OpenFeature `EvaluationContext` is mapped to the Unleash context as follows:

- `EvaluationContext.targeting_key` → Unleash `userId`
- `EvaluationContext.attributes` → merged into the Unleash context as-is

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
provider.add_handler(
    ProviderEvent.PROVIDER_CONFIGURATION_CHANGED, on_configuration_changed
)

# Remove event handlers
provider.remove_handler(ProviderEvent.PROVIDER_READY, on_provider_ready)
```

**Supported events:**
- `ProviderEvent.PROVIDER_READY`: Emitted when the provider is ready to evaluate flags
- `ProviderEvent.PROVIDER_ERROR`: Emitted when the provider encounters an error
- `ProviderEvent.PROVIDER_CONFIGURATION_CHANGED`: Emitted when flag configurations are updated

Note: `ProviderEvent.PROVIDER_STALE` handlers can be registered but are not currently emitted by this provider.

### Supported flag types

This provider supports resolving the following types via the OpenFeature client:

- Boolean (`get_boolean_value`/`details`): uses `UnleashClient.is_enabled`
- String (`get_string_value`/`details`): from variant payload
- Integer (`get_integer_value`/`details`): from variant payload
- Float (`get_float_value`/`details`): from variant payload
- Object (`get_object_value`/`details`): from variant payload, JSON-parsed if needed

### Example usage

```python
from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider
from openfeature.evaluation_context import EvaluationContext

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
context = EvaluationContext(targeting_key="user123", attributes={"sessionId": "session456"})
variant = client.get_string_value("my-variant-flag", "default", context)
print(f"Variant: {variant}")

# Shutdown when done
provider.shutdown()
```

## Development

### Running tests

```bash
uv run test --frozen
```

Integration tests require Docker to be installed and running. To run only integration tests:

```bash
uv run test -m integration --frozen
```

To skip integration tests:

```bash
uv run test -m "not integration" --frozen
```

### Type checking

```bash
uv run mypy-check
```

### Linting

Run Ruff checks:

```bash
uv run ruff check
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
