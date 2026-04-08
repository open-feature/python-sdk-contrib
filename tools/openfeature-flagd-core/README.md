# OpenFeature flagd Core

Reference implementation of the flagd evaluator -- flag parsing, targeting rules (JSON logic), and custom operators (fractional, sem_ver, starts_with, ends_with). Mirrors the Java `flagd-core` module.

It is part of the [OpenFeature Python SDK contrib](https://github.com/open-feature/python-sdk-contrib) project.

## Installation

```bash
pip install openfeature-flagd-core
```

## Usage

```python
from openfeature.contrib.tools.flagd.core import FlagdCore

core = FlagdCore()
core.set_flags('{"flags": {"my-flag": {"state": "ENABLED", "variants": {"on": true}, "defaultVariant": "on"}}}')
result = core.resolve_boolean_value("my-flag", False)
```

## License

Apache 2.0 - See [LICENSE](./LICENSE) for details.
