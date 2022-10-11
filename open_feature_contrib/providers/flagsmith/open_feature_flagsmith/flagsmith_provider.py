import os
from numbers import Number

from flagsmith.flagsmith import Flagsmith
from open_feature_sdk.provider.provider import AbstractProvider
from open_feature_sdk.evaluation_context.evaluation_context import EvaluationContext
from open_feature_sdk.flag_evaluation.flag_evaluation_details import FlagEvaluationDetails

from open_feature_contrib.providers.flagsmith.open_feature_flagsmith.exceptions import FlagsmithConfigurationError


class FlagsmithProvider(AbstractProvider):

    def __init__(
        self,
        enable_local_evaluation: bool = False,
        api_url: str = None,
        request_timeout_seconds: int = None,
        environment_refresh_interval_seconds: int = None,
        retries: int = None,
        enable_analytics: bool = False,
        custom_headers: dict = None,
    ):
        kwargs = {}
        if environment_key := os.environ.get("FLAGSMITH_ENVIRONMENT_KEY"):
            kwargs["environment_key"] = environment_key
        else:
            raise FlagsmithConfigurationError("No environment key set for Flagsmith")

        for arg in locals():
            kwargs[arg.title] = arg

        self.flagsmith = Flagsmith(**kwargs)

    def get_name(self) -> str:
        return "Flagsmith"

    def get_boolean_details(
        self,
        key: str,
        default_value: bool,
        evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        flag = self._get_flag(key, default_value, evaluation_context)
        if isinstance(flag, bool):
            return FlagEvaluationDetails(key, flag)
        else:
            raise TypeMismatchError()

    def get_string_details(
        self,
        key: str,
        default_value: str,
        evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        flag = self._get_flag(key, default_value, evaluation_context)
        if isinstance(flag, str):
            return FlagEvaluationDetails(key, flag)
        else:
            raise TypeMismatchError()

    def get_number_details(
        self,
        key: str,
        default_value: Number,
        evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        flag = self._get_flag(key, default_value, evaluation_context)
        if isinstance(flag, Number):
            return FlagEvaluationDetails(key, flag)
        else:
            raise TypeMismatchError()

    def get_object_details(
        self,
        key: str,
        default_value: dict,
        evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        flag = self._get_flag(key, default_value, evaluation_context)
        if isinstance(flag, dict):
            return FlagEvaluationDetails(key, flag)
        else:
            raise TypeMismatchError()

    def _get_flag(
        self,
        key: str,
        default_value,
        evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        flags = self._get_flags(evaluation_context)
        if flags.is_feature_enabled(key):
            return flags.get_feature_value(key)
        else:
            return default_value

    def _get_flags(self, evaluation_context: EvaluationContext = EvaluationContext()):
        kwargs = {
            "identifier": evaluation_context.attrubutes.get("identifier"),
            "traits": evaluation_context.attrubutes.get("traits"),
        }

        if kwargs.get("identifier") or kwargs.get("traits"):
            return self.flagsmith.get_identity_flags(**kwargs)
        return self.flagsmith.get_environment_flags()
