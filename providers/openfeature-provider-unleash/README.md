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

api.set_provider(UnleashProvider())
```

### Configuration options

<!-- TODO: add configuration options -->

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
