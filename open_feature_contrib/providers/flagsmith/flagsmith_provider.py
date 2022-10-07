from numbers import Number

from open_feature_sdk.provider.provider import AbstractProvider
from open_feature_sdk.evaluation_context.evaluation_context import EvaluationContext

class FlagsmithProvider(AbstractProvider):

    def __init__(self, api_key: str):
        self.api_key = api_key if api_key else os.environ.get("FLAGSMITH_ENVIRONMENT_KEY")

        self.flagsmith = Flagsmith(
            environment_key=self.api_key,
            enable_local_evaluation=False,
            api_url="https://api.yourselfhostedflagsmith.com/api/v1/",
            request_timeout_seconds=10,
            environment_refresh_interval_seconds= 60,
            retries=None,
            enable_analytics= False,
            custom_headers = None,
            default_flag_handler=DefaultFlag(enabled=False, value=None)
        )

    def get_name(self) -> str:
        return "Flagsmith"

    def get_boolean_details(
            self,
            key: str,
            default_value: bool,
            evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        pass

    def get_string_details(
            self,
            key: str,
            default_value: str,
            evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        pass

    def get_number_details(
            self,
            key: str,
            default_value: Number,
            evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        pass

    def get_object_details(
            self,
            key: str,
            default_value: dict,
            evaluation_context: EvaluationContext = EvaluationContext(),
    ):
        pass
