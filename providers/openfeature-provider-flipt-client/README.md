# OpenFeature Flipt Client-Side Provider

This provider is designed to support client side evaluation of feature flags for Flipt feature flag provider.

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install openfeature-provider-flipt-client
```

## Configuration

```python
from openfeature.contrib.provider.flipt_client import (
    FliptClientProvider,
)

FliptClientProvider(
    base_url="",
    Client
)


```



## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
