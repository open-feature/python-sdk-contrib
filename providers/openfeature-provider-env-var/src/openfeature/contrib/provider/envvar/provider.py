import json
import typing
import os

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import FlagNotFoundError
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.provider import AbstractProvider, Metadata


def _load_and_parse_env_var(
    flag_key: str, parse: typing.Callable[[str], typing.Any]
) -> FlagResolutionDetails:
    value = os.environ.get(flag_key)
    if value is None:
        raise FlagNotFoundError()
    return FlagResolutionDetails(parse(value), None, None, Reason.DEFAULT, None, {})


class EnvVarProvider(AbstractProvider):
    def get_metadata(self) -> Metadata:
        return Metadata(name="EnvVarProvider")

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return _load_and_parse_env_var(flag_key, lambda v: bool(v))

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return _load_and_parse_env_var(flag_key, lambda v: v)

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return _load_and_parse_env_var(flag_key, lambda v: int(v))

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return _load_and_parse_env_var(flag_key, lambda v: float(v))

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: typing.Union[dict, list],
        evaluation_context: typing.Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[typing.Union[dict, list]]:
        def parse(value: str) -> typing.Union[dict, list]:
            result = json.loads(value)
            if isinstance(result, dict) or isinstance(result, list):
                return result
            else:
                raise TypeError(
                    f'Value for feature flag with key "${flag_key}" does not resolve to a JSON object or list'
                )

        return _load_and_parse_env_var(flag_key, parse)
