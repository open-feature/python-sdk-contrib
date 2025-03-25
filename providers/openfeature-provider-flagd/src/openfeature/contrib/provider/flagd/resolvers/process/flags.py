import json
import re
import typing
from dataclasses import dataclass

from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError


def _validate_metadata(key: str, value: typing.Union[float, int, str, bool]) -> None:
    if key is None:
        raise ParseError("Metadata key must be set")
    elif not isinstance(key, str):
        raise ParseError(f"Metadata key {key} must be of type str, but is {type(key)}")
    elif not key:
        raise ParseError("key must not be empty")
    if value is None:
        raise ParseError(f"Metadata value for key {key} must be set")
    elif not isinstance(value, (float, int, str, bool)):
        raise ParseError(
            f"Metadata value {value} for key  {key} must be of type float, int, str or bool, but is {type(value)}"
        )


class FlagStore:
    def __init__(
        self,
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.emit_provider_configuration_changed = emit_provider_configuration_changed
        self.flags: typing.Mapping[str, Flag] = {}
        self.flag_set_metadata: typing.Mapping[
            str, typing.Union[float, int, str, bool]
        ] = {}

    def get_flag(self, key: str) -> typing.Optional["Flag"]:
        return self.flags.get(key)

    def update(self, flags_data: dict) -> None:
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

        self.flags = {key: Flag.from_dict(key, data) for key, data in flags.items()}
        self.flag_set_metadata = metadata

        self.emit_provider_configuration_changed(
            ProviderEventDetails(
                flags_changed=list(self.flags.keys()), metadata=metadata
            )
        )


@dataclass
class Flag:
    key: str
    state: str
    variants: typing.Mapping[str, typing.Any]
    default_variant: typing.Union[bool, str]
    targeting: typing.Optional[dict] = None
    metadata: typing.Optional[
        typing.Mapping[str, typing.Union[float, int, str, bool]]
    ] = None

    def __post_init__(self) -> None:
        if not self.state or not isinstance(self.state, str):
            raise ParseError("Incorrect 'state' value provided in flag config")

        if not self.variants or not isinstance(self.variants, dict):
            raise ParseError("Incorrect 'variants' value provided in flag config")

        if not self.default_variant or not isinstance(
            self.default_variant, (str, bool)
        ):
            raise ParseError("Incorrect 'defaultVariant' value provided in flag config")

        if self.targeting and not isinstance(self.targeting, dict):
            raise ParseError("Incorrect 'targeting' value provided in flag config")

        if self.default_variant not in self.variants:
            raise ParseError("Default variant does not match set of variants")

        if self.metadata:
            if not isinstance(self.metadata, dict):
                raise ParseError("Flag metadata is not a valid json object")
            for key, value in self.metadata.items():
                _validate_metadata(key, value)

    @classmethod
    def from_dict(cls, key: str, data: dict) -> "Flag":
        if "defaultVariant" in data:
            data["default_variant"] = data["defaultVariant"]
            del data["defaultVariant"]

        data.pop("source", None)
        data.pop("selector", None)
        try:
            flag = cls(key=key, **data)
            return flag
        except ParseError as parseError:
            raise parseError
        except Exception as err:
            raise ParseError from err

    @property
    def default(self) -> tuple[str, typing.Any]:
        return self.get_variant(self.default_variant)

    def get_variant(
        self, variant_key: typing.Union[str, bool]
    ) -> tuple[str, typing.Any]:
        if isinstance(variant_key, bool):
            variant_key = str(variant_key).lower()

        return variant_key, self.variants.get(variant_key)
