"""Validation of flag configurations against the bundled flagd JSON schema.

The schema files in ``schemas/`` are copies of ``json/flags.json`` and
``json/targeting.json`` from https://github.com/open-feature/schemas, which the
flagd provider already checks out as a git submodule. Run ``poe sync-schemas``
to refresh them after updating that submodule.
"""

import json
import typing
from collections.abc import Mapping
from functools import cache
from importlib.resources import files

from jsonschema import Draft7Validator
from referencing import Registry, Resource

_SCHEMA_FILES = ("flags.json", "targeting.json")
_FLAGS_SCHEMA_ID = "https://flagd.dev/schema/v0/flags.json"


@cache
def _validator() -> Draft7Validator:
    schema_dir = files(__package__).joinpath("schemas")
    schemas = [
        json.loads(schema_dir.joinpath(name).read_text(encoding="utf-8"))
        for name in _SCHEMA_FILES
    ]
    # flags.json references targeting.json by a relative "$ref", which resolves
    # against the "$id" of flags.json. flags.json also has a top-level "$ref",
    # and draft-07 ignores keywords next to "$ref", including "$id". So each
    # schema is registered under the "$id" read from the file, and validation
    # starts from a "$ref" to that URI, giving relative references a base.
    registry: Registry[typing.Any] = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    return Draft7Validator({"$ref": _FLAGS_SCHEMA_ID}, registry=registry)


def validate_flag_configuration(configuration: Mapping[str, typing.Any]) -> list[str]:
    """Validate a flag configuration against the flagd JSON schema.

    Returns a description of every schema violation, or an empty list if the
    configuration is valid. Each description names the location and the failed
    schema keyword only: ``jsonschema`` messages embed the offending instance,
    which could leak variant values or targeting literals into logs.
    """
    errors = sorted(
        _validator().iter_errors(configuration), key=lambda error: error.json_path
    )
    return [
        f"{error.json_path}: does not match the schema ('{error.validator}')"
        for error in errors
    ]
