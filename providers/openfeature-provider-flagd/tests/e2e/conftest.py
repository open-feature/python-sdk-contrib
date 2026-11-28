import pytest

from tests.e2e.step.config_steps import *  # noqa: F403
from tests.e2e.step.context_steps import *  # noqa: F403
from tests.e2e.step.event_steps import *  # noqa: F403
from tests.e2e.step.flag_step import *  # noqa: F403
from tests.e2e.step.provider_steps import *  # noqa: F403

# Python's JsonLogic raises ZeroDivisionError for x/0, where the other cores compute
# Infinity or NaN, so the flag never reaches resolve's non-finite metadata check
SKIPPED_SCENARIOS = {
    "Resolve with a non-finite computed number in metadata falls back to the default variant",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        scenario = getattr(getattr(item, "obj", None), "__scenario__", None)
        if scenario is not None and scenario.name in SKIPPED_SCENARIOS:
            item.add_marker(pytest.mark.skip(reason="JsonLogic raises on x/0"))
