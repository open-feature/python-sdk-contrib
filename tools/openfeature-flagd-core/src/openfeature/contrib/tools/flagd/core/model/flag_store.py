import json
import re
import typing

from openfeature.exception import ParseError

from .flag import Flag, _validate_metadata


class FlagStore:
    def __init__(self) -> None:
        self.flags: typing.Mapping[str, Flag] = {}
        self.flag_set_metadata: typing.Mapping[
            str, typing.Union[float, int, str, bool]
        ] = {}

    def get_flag(self, key: str) -> typing.Optional[Flag]:
        return self.flags.get(key)

    def update(self, flags_data: dict) -> typing.List[str]:
        """Update flags and return list of changed flag keys."""
        flags = flags_data.get("flags", {})
        metadata = flags_data.get("metadata", {})
        evaluators: typing.Optional[dict] = flags_data.get("$evaluators")
        if evaluators:
            transposed = json.dumps(flags)
            for name, rule in evaluators.items():
                transposed = re.sub(
                    rf"{{\s*\"\$ref\":\s*\"{name}\"\s*}}", json.dumps(rule), transposed
                )
            flags = json.loads(transposed)

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
        for key in new_keys.intersection(old_keys):
            if new_flags[key] != self.flags.get(key):
                changed_keys.append(key)

        self.flags = new_flags
        self.flag_set_metadata = metadata

        return changed_keys
