# OpenFeature flagd Evaluator API

This package defines the pure API/contract (Python Protocol) for the flagd evaluator, allowing others to provide their own evaluator implementations.

It is part of the [OpenFeature Python SDK contrib](https://github.com/open-feature/python-sdk-contrib) project and mirrors the Java `flagd-api` module.

## Installation

```bash
pip install openfeature-flagd-api
```

## Usage

```python
from openfeature.contrib.tools.flagd.api import Evaluator, FlagStoreException
```

Implement the `Evaluator` protocol to create a custom evaluator for the flagd provider.

## License

Apache 2.0 - See [LICENSE](./LICENSE) for details.
