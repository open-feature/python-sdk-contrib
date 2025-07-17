import json
import re
import typing
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft7Validator, ValidationError
from referencing import Registry, Resource

from openfeature.event import ProviderEventDetails
from openfeature.exception import ParseError

project_root = Path(__file__).resolve().parents[7]
SCHEMAS = project_root / "openfeature/schemas/json"


def retrieve_from_filesystem(uri: str) -> Resource:
    path = SCHEMAS / Path(uri.removeprefix("https://flagd.dev/schema/v0/"))
    contents = json.loads(path.read_text())
    return Resource.from_contents(contents)


registry = Registry(retrieve=retrieve_from_filesystem)  # type: ignore[call-arg]

validator = Draft7Validator(
    registry=registry,
    schema={"$ref": "https://flagd.dev/schema/v0/flags.json"},
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
        try:
            validator.validate(flags_data)
        except ValidationError as e:
            raise ParseError(e.message) from e

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
