# OFREP Provider for OpenFeature

This provider is designed to use the [OpenFeature Remote Evaluation Protocol (OFREP)](https://openfeature.dev/specification/appendix-c).

## Installation

```
pip install openfeature-provider-ofrep
```

## Configuration and Usage

Instantiate a new OFREPProvider instance and configure the OpenFeature SDK to use it:

```python
from openfeature import api
from openfeature.contrib.provider.ofrep import OFREPProvider

api.set_provider(OFREPProvider("http://localhost:2321"))
```

### Configuration options

| Option            | Environment variable | Description                                                                                                                                        | Type                           | Default |
| ----------------- | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ------- |
| `base_url`        | `OFREP_ENDPOINT`     | OFREP server endpoint, e.g. `http://localhost:2321`                                                                                                | `str`                          | -       |
| `headers_factory` | `OFREP_HEADERS`      | Headers sent with each request. The environment variable is a comma-separated list of `key=value` pairs, e.g. `Authorization=Bearer 123,X-Env=prod` | `Callable[[], dict[str, str]]` | -       |
| `timeout`         | `OFREP_TIMEOUT_MS`   | Request timeout. The argument is in seconds, the environment variable in milliseconds                                                              | `float`                        | 5 s     |

Arguments passed to `OFREPProvider` take precedence over environment variables. When `headers_factory` is
given, `OFREP_HEADERS` is ignored. An unset or blank environment variable is treated as not set, and an
invalid value raises a `ValueError`.

```python
# OFREP_ENDPOINT=http://localhost:2321 OFREP_TIMEOUT_MS=2000
api.set_provider(OFREPProvider())
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
