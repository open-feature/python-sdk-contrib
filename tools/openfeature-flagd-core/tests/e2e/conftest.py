import pytest

from openfeature.contrib.tools.flagd.core import FlagdCore
from openfeature.contrib.tools.flagd.testkit import load_testkit_flags
from openfeature.contrib.tools.flagd.testkit.steps import *  # noqa: F403


@pytest.fixture
def evaluator():
    """Create a FlagdCore evaluator loaded with testkit flags."""
    core = FlagdCore()
    core.set_flags(load_testkit_flags())
    return core
