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

api.set_provider(OFREPProvider())
```

### Configuration options

<!-- TODO: add configuration options -->

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
