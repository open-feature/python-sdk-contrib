import json
from pathlib import Path

import pytest
from pytest_bdd import scenarios

from openfeature.contrib.tools.flagd.core import FlagdCore
from openfeature.contrib.tools.flagd.testkit.steps import *  # noqa: F403

scenarios(str(Path(__file__).parent / "features"))

_DISABLED_FLAGS = json.dumps(
    {
        "flags": {
            "disabled-boolean-flag": {
                "state": "DISABLED",
                "variants": {"on": True, "off": False},
                "defaultVariant": "on",
            },
            "disabled-string-flag": {
                "state": "DISABLED",
                "variants": {"greeting": "hi", "parting": "bye"},
                "defaultVariant": "greeting",
            },
            "disabled-integer-flag": {
                "state": "DISABLED",
                "variants": {"one": 1, "ten": 10},
                "defaultVariant": "ten",
            },
            "disabled-float-flag": {
                "state": "DISABLED",
                "variants": {"tenth": 0.1, "half": 0.5},
                "defaultVariant": "half",
            },
            "disabled-object-flag": {
                "state": "DISABLED",
                "variants": {
                    "empty": {},
                    "template": {
                        "showImages": True,
                        "title": "Check out these pics!",
                        "imagesPerPage": 100,
                    },
                },
                "defaultVariant": "template",
            },
        }
    }
)


@pytest.fixture
def evaluator():
    core = FlagdCore()
    core.set_flags(_DISABLED_FLAGS)
    return core
