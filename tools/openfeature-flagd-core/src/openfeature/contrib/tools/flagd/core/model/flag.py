import typing
from collections.abc import Mapping
from dataclasses import dataclass

from openfeature.exception import ParseError


def _validate_metadata(key: str, value: float | int | str | bool) -> None:
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


@dataclass
class Flag:
    key: str
    state: str
    variants: Mapping[str, typing.Any]
    default_variant: bool | str | None = None
    targeting: dict | None = None
    metadata: Mapping[str, float | int | str | bool] | None = None

    def __post_init__(self) -> None:
        if not self.state or not (self.state == "ENABLED" or self.state == "DISABLED"):
            raise ParseError("Incorrect 'state' value provided in flag config")

        if not self.variants or not isinstance(self.variants, dict):
            raise ParseError("Incorrect 'variants' value provided in flag config")

        if self.default_variant and not isinstance(self.default_variant, (str, bool)):
            raise ParseError("Incorrect 'defaultVariant' value provided in flag config")

        if self.metadata:
            if not isinstance(self.metadata, dict):
                raise ParseError("Flag metadata is not a valid json object")
            for key, value in self.metadata.items():
                _validate_metadata(key, value)

    @classmethod
    def from_dict(cls, key: str, data: dict) -> "Flag":
        if "defaultVariant" in data:
            data["default_variant"] = data["defaultVariant"]
            if data["default_variant"] == "":
                data["default_variant"] = None
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
    def default(self) -> tuple[str | None, typing.Any]:
        return self.get_variant(self.default_variant)

    def get_variant(
        self, variant_key: str | bool | None
    ) -> tuple[str | None, typing.Any]:
        if isinstance(variant_key, bool):
            variant_key = str(variant_key).lower()

        if not variant_key:
            return None, None

        return variant_key, self.variants.get(variant_key)
