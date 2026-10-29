import copy
import json
import logging
from pathlib import Path

import pytest

from openfeature.contrib.tools.flagd.core import FlagdCore
from openfeature.contrib.tools.flagd.core.schema import validate_flag_configuration
from openfeature.flag_evaluation import Reason

SCHEMAS_SUBMODULE = (
    Path(__file__).parents[3]
    / "providers/openfeature-provider-flagd/openfeature/schemas/json"
)
BUNDLED_SCHEMAS = (
    Path(__file__).parents[1] / "src/openfeature/contrib/tools/flagd/core/schemas"
)

requires_submodule = pytest.mark.skipif(
    not SCHEMAS_SUBMODULE.exists(), reason="schemas submodule is not checked out"
)

VALID_CONFIG = {
    "flags": {
        "my-flag": {
            "state": "ENABLED",
            "variants": {"on": True, "off": False},
            "defaultVariant": "on",
        }
    }
}

# Parses fine, so it is applied, but variants of mixed types break the schema.
INVALID_CONFIG = {
    "flags": {
        "mixed-flag": {
            "state": "ENABLED",
            "variants": {"on": True, "off": "no"},
            "defaultVariant": "on",
        }
    }
}

CONFIG_WITH_EVALUATORS = {
    "$evaluators": {
        "is-admin": {"in": ["admin", {"var": "role"}]},
    },
    "flags": {
        "targeted-flag": {
            "state": "ENABLED",
            "variants": {"on": True, "off": False},
            "defaultVariant": "off",
            "targeting": {"if": [{"$ref": "is-admin"}, "on", "off"]},
        }
    },
}


def _fixtures(kind: str) -> list[Path]:
    """Fixtures from the schemas repo that target flags.json.

    Each fixture names its schema in "$schema"; some target the flagd daemon
    schema (flagd.json) instead, which flagd-core does not validate against.
    """
    if not SCHEMAS_SUBMODULE.exists():
        return []
    return [
        path
        for path in sorted((SCHEMAS_SUBMODULE / "test/flags" / kind).glob("*.json"))
        if json.loads(path.read_text(encoding="utf-8"))
        .get("$schema", "")
        .endswith("/flags.json")
    ]


def _schema_warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.levelno == logging.WARNING and "flagd schema" in record.message
    ]


@requires_submodule
@pytest.mark.parametrize("path", _fixtures("positive"), ids=lambda path: path.name)
def test_valid_schema_fixtures_pass(path: Path) -> None:
    assert (
        validate_flag_configuration(json.loads(path.read_text(encoding="utf-8"))) == []
    )


@requires_submodule
@pytest.mark.parametrize("path", _fixtures("negative"), ids=lambda path: path.name)
def test_invalid_schema_fixtures_fail(path: Path) -> None:
    assert (
        validate_flag_configuration(json.loads(path.read_text(encoding="utf-8"))) != []
    )


@requires_submodule
@pytest.mark.parametrize("name", ["flags.json", "targeting.json"])
def test_bundled_schemas_match_submodule(name: str) -> None:
    bundled = json.loads((BUNDLED_SCHEMAS / name).read_text(encoding="utf-8"))
    upstream = json.loads((SCHEMAS_SUBMODULE / name).read_text(encoding="utf-8"))
    assert bundled == upstream, f"Run `poe sync-schemas` to update {name}"


def test_errors_point_to_the_invalid_field() -> None:
    errors = validate_flag_configuration(INVALID_CONFIG)

    assert errors
    assert all(error.startswith("$.flags['mixed-flag']") for error in errors)


def test_valid_config_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        FlagdCore().set_flags(json.dumps(VALID_CONFIG))

    assert _schema_warnings(caplog) == []


def test_evaluator_refs_are_resolved_before_validation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    core = FlagdCore()
    with caplog.at_level(logging.WARNING):
        core.set_flags(json.dumps(CONFIG_WITH_EVALUATORS))

    assert _schema_warnings(caplog) == []


def test_invalid_config_warns_and_is_still_applied(
    caplog: pytest.LogCaptureFixture,
) -> None:
    core = FlagdCore()
    with caplog.at_level(logging.WARNING):
        core.set_flags(json.dumps(INVALID_CONFIG))

    warnings = _schema_warnings(caplog)
    assert len(warnings) == 1
    assert "$.flags['mixed-flag']" in warnings[0].message

    result = core.resolve_boolean_value("mixed-flag", False)
    assert result.value is True
    assert result.reason == Reason.STATIC


def test_invalid_config_warns_when_getting_changed_keys(
    caplog: pytest.LogCaptureFixture,
) -> None:
    core = FlagdCore()
    with caplog.at_level(logging.WARNING):
        changed = core.set_flags_and_get_changed_keys(copy.deepcopy(INVALID_CONFIG))

    assert changed == ["mixed-flag"]
    assert len(_schema_warnings(caplog)) == 1


def test_invalid_flag_does_not_block_other_flags(
    caplog: pytest.LogCaptureFixture,
) -> None:
    config = copy.deepcopy(
        {"flags": {**VALID_CONFIG["flags"], **INVALID_CONFIG["flags"]}}
    )
    core = FlagdCore()
    with caplog.at_level(logging.WARNING):
        core.set_flags(config)

    assert len(_schema_warnings(caplog)) == 1
    assert core.resolve_boolean_value("my-flag", False).value is True
