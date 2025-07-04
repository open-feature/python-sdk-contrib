# A OpenFeature Python Environment Variable Provider

This provider loads flag values from environment variables.
If a flag with some key is evaluated when no env var named after this key exists, it will throw a `FlagNotFoundError`.
Otherwise it will attempt to parse the string value of the env var to the appropriate type (`str`,`int`,`float`, or object).
Errors during this parsing are forwarded to the user.

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