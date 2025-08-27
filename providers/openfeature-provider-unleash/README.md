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

# Resolve different types of flags
boolean_flag = client.get_boolean_details("my-boolean-flag", default_value=False)
string_flag = client.get_string_details("my-string-flag", default_value="default")
integer_flag = client.get_integer_details("my-integer-flag", default_value=0)
float_flag = client.get_float_details("my-float-flag", default_value=0.0)
object_flag = client.get_object_details("my-object-flag", default_value={"key": "value"})

# Check flag values
if boolean_flag.value:
    print("Boolean feature is enabled!")

print(f"String value: {string_flag.value}")
print(f"Integer value: {integer_flag.value}")
print(f"Float value: {float_flag.value}")
print(f"Object value: {object_flag.value}")

# Clean up when done
provider.shutdown()
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
