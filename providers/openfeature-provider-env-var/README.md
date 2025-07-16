# A OpenFeature Python Environment Variable Provider

This provider loads flag values from environment variables.
If a flag with some key is evaluated when no env var named after this key exists, it will throw a `FlagNotFoundError`.
Otherwise it will attempt to parse the string value of the env var to the appropriate type (`str`,`int`,`float`, or object).
Errors during this parsing are forwarded to the user.

## Installation

```console
pip install openfeature-provider-env-var
```

## Usage

Create a new instance of the `EnvVarProvider`:

```Python
provider = EnvVarProvider()
```

Configure the OpenFeature API to use the `EnvVarProvider` and retrieve the client:

```Python
from openfeature import api
from openfeature.contrib.provider.envvar import EnvVarProvider

api.set_provider(EnvVarProvider())
client = api.get_client()
result = client.get_boolean_value("<your feature flag key>", True)
```

The `EnvVarProvider` will attempt to read values from the present environment variables.
If no values is present for a flag key, it will throw a `FlagNotFoundError`.
Otherwise, it will attempt to parse the value associated with the key to the requested type (e.g. `float` in the case of
`provider.resolve_float_details(key, 0.0, None)`) and forward any error that is raised during parsing to the user.
Note that any such errors will be caught by the OpenFeature API and translated into appropriate error codes.

## Build setup

This provider uses uv as build tool.

### Building

```shell
uv build
```

### Executing tests

```shell
uv run pytest
```

#### pre commit hooks

Install the pre commit hooks that ensure proper formatting:

```shell
uvx pre-commit install
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
