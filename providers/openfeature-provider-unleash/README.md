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

# Resolve different types of flags (synchronous)
boolean_flag = client.get_boolean_details("my-boolean-flag", default_value=False)
string_flag = client.get_string_details("my-string-flag", default_value="default")
integer_flag = client.get_integer_details("my-integer-flag", default_value=0)
float_flag = client.get_float_details("my-float-flag", default_value=0.0)
object_flag = client.get_object_details("my-object-flag", default_value={"key": "value"})

# Resolve different types of flags (asynchronous)
boolean_flag_async = await client.get_boolean_details_async("my-boolean-flag", default_value=False)
string_flag_async = await client.get_string_details_async("my-string-flag", default_value="default")
integer_flag_async = await client.get_integer_details_async("my-integer-flag", default_value=0)
float_flag_async = await client.get_float_details_async("my-float-flag", default_value=0.0)
object_flag_async = await client.get_object_details_async("my-object-flag", default_value={"key": "value"})

# Using evaluation context for targeting
from openfeature.evaluation_context import EvaluationContext

context = EvaluationContext(
    targeting_key="user123",
    attributes={"email": "user@example.com", "country": "US", "plan": "premium"}
)

# Resolve flags with context (synchronous)
boolean_with_context = client.get_boolean_details("my-boolean-flag", default_value=False, evaluation_context=context)
string_with_context = client.get_string_details("my-string-flag", default_value="default", evaluation_context=context)

# Resolve flags with context (asynchronous)
boolean_async_with_context = await client.get_boolean_details_async("my-boolean-flag", default_value=False, evaluation_context=context)
string_async_with_context = await client.get_string_details_async("my-string-flag", default_value="default", evaluation_context=context)

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
