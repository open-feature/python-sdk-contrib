# OpenFeature flagd API Testkit

A compliance test suite for the flagd Evaluator protocol. This package bundles Gherkin feature files and pytest-bdd step definitions so that any implementation of the Evaluator protocol can run the full compliance suite.

## Usage

1. Add `openfeature-flagd-api-testkit` as a test dependency.

2. Create a `conftest.py` that provides an `evaluator` fixture and imports the bundled steps:

```python
import pytest
from openfeature.contrib.tools.flagd.testkit import load_testkit_flags
from openfeature.contrib.tools.flagd.testkit.steps import *  # noqa: F401, F403


@pytest.fixture
def evaluator():
    """Provide your Evaluator implementation here."""
    e = MyEvaluator()
    e.set_flags(load_testkit_flags())
    return e
```

3. Create a test file that registers scenarios from the bundled feature files:

```python
from pytest_bdd import scenarios
from openfeature.contrib.tools.flagd.testkit import get_features_path

scenarios(get_features_path())
```
