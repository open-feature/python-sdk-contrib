import logging
import time
from pathlib import Path

import pytest
from pytest_bdd import parsers, scenario, when
from tests.conftest import setup_flag_file

GHERKIN_FOLDER = "../../../../test-harness/gherkin/"


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Provider ready event")
def test_ready_event(caplog):
    """Provider ready event"""
    caplog.set_level(logging.DEBUG)


@scenario(f"{GHERKIN_FOLDER}flagd.feature", "Flag change event")
def test_change_event():
    """Flag change event"""


@pytest.fixture
def flag_file(tmp_path):
    return setup_flag_file(tmp_path, "changing-flag-bar.json")


@when(parsers.cfparse('a flag with key "{key}" is modified'))
def modify_flag(flag_file, key):
    time.sleep(0.1)  # guard against race condition
    contents = (
        Path(__file__).parent / "../../../../test-harness/flags/changing-flag-foo.json"
    ).read_text()
    with open(flag_file, "w") as f:
        f.write(contents)
