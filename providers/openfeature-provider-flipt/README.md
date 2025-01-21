# OpenFeature Flipt OFREP Provider

This provider is designed to evaluate feature flags against the Flipt api using Flipt's [OpenFeature remote evaluation protocol (OFREP)](https://docs.flipt.io/reference/openfeature/overview) API.
This provider performs flag evaluations via HTTP.

-----

## Table of Contents

- [Installation](#installation)
- [License](#license)

## Installation

```console
pip install openfeature-provider-flipt
```

## Configuration

```python
from openfeature import api
from openfeature.contrib.provider.flipt import FliptProvider

api.set_provider(FliptProvider(base_url="<flipt instance>", namespace="<your flipt feature flag namespace>"))
client = api.get_client()
client.get_boolean_value("<your feature flag key>", True)
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for more information.
