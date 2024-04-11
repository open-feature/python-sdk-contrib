import typing
from dataclasses import dataclass

from openfeature.exception import ParseError


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
        data["default_variant"] = data["defaultVariant"]
        del data["defaultVariant"]
        flag = cls(key=key, **data)

        return flag

    @property
    def default(self) -> typing.Tuple[str, typing.Any]:
        return self.get_variant(self.default_variant)

    def get_variant(
        self, variant_key: typing.Union[str, bool]
    ) -> typing.Tuple[str, typing.Any]:
        if isinstance(variant_key, bool):
            variant_key = str(variant_key).lower()

        return variant_key, self.variants.get(variant_key)
