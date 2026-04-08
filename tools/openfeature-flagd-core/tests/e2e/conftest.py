import pytest

from openfeature.contrib.tools.flagd.testkit import load_testkit_flags
from openfeature.contrib.tools.flagd.testkit.steps import *  # noqa: F401, F403
from openfeature.contrib.tools.flagd.core import FlagdCore


@pytest.fixture
def evaluator():
    """Create a FlagdCore evaluator loaded with testkit flags."""
    core = FlagdCore()
    core.set_flags(load_testkit_flags())
    return core
