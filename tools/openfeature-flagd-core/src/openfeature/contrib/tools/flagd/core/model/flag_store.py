import json
import logging
import re
from collections.abc import Mapping

from openfeature.exception import ParseError

from ..schema import validate_flag_configuration
from .flag import Flag, _validate_metadata

logger = logging.getLogger("openfeature.contrib")


class FlagStore:
    def __init__(self) -> None:
        self.flags: Mapping[str, Flag] = {}
        self.flag_set_metadata: Mapping[str, float | int | str | bool] = {}

    def get_flag(self, key: str) -> Flag | None:
        return self.flags.get(key)

    def update(self, flags_data: dict) -> list[str]:
        """Update flags and return list of changed flag keys."""
        flags = flags_data.get("flags", {})
        metadata = flags_data.get("metadata", {})
        evaluators: dict | None = flags_data.get("$evaluators")
        if evaluators:
            transposed = json.dumps(flags)
            for name, rule in evaluators.items():
                transposed = re.sub(
                    rf"{{\s*\"\$ref\":\s*\"{re.escape(name)}\"\s*}}",
                    json.dumps(rule),
                    transposed,
                )
            flags = json.loads(transposed)

        # Like the other flagd cores, an invalid configuration is only reported:
        # rejecting it would block updates to every other flag in the set.
        schema_errors = validate_flag_configuration(
            {**flags_data, "flags": flags} if evaluators else flags_data
        )
        if schema_errors:
            logger.warning(
                "Flag configuration does not match the flagd schema, applying it anyway:\n%s",
                "\n".join(schema_errors),
            )

        if not isinstance(flags, dict):
            raise ParseError("`flags` key of configuration must be a dictionary")
        if not isinstance(metadata, dict):
            raise ParseError("`metadata` key of configuration must be a dictionary")
        for key, value in metadata.items():
            _validate_metadata(key, value)

        old_keys = set(self.flags.keys())
        new_flags = {key: Flag.from_dict(key, data) for key, data in flags.items()}
        new_keys = set(new_flags.keys())

        # Determine changed keys
        changed_keys = list(new_keys.symmetric_difference(old_keys))
        changed_keys.extend(
            key
            for key in new_keys.intersection(old_keys)
            if new_flags[key] != self.flags.get(key)
        )

        self.flags = new_flags
        self.flag_set_metadata = metadata

        return changed_keys
