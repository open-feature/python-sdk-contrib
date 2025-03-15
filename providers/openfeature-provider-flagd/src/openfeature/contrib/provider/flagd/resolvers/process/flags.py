import json
import re
import typing
from dataclasses import dataclass

from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError


class FlagStore:
    def __init__(
        self,
        emit_provider_configuration_changed: typing.Callable[
            [ProviderEventDetails], None
        ],
    ):
        self.emit_provider_configuration_changed = emit_provider_configuration_changed
        self.flags: typing.Mapping[str, Flag] = {}

    def get_flag(self, key: str) -> typing.Optional["Flag"]:
        return self.flags.get(key)

    def update(self, flags_data: dict) -> None:
        flags = flags_data.get("flags", {})
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
        self.flags = {key: Flag.from_dict(key, data) for key, data in flags.items()}

        self.emit_provider_configuration_changed(
            ProviderEventDetails(flags_changed=list(self.flags.keys()))
        )


@dataclass
class Flag:
    key: str
    state: str
    variants: typing.Mapping[str, typing.Any]
    default_variant: typing.Union[bool, str]
    targeting: typing.Optional[dict] = None

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
