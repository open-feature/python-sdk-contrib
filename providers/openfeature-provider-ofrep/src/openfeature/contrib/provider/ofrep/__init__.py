from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests
from requests.exceptions import JSONDecodeError

from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    ErrorCode,
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    OpenFeatureError,
    ParseError,
    TargetingKeyMissingError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata

__all__ = ["OFREPProvider"]


class OFREPProvider(AbstractProvider):
    def __init__(
        self,
        base_url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
    ):
        self.base_url = base_url
        self.headers = headers
        self.timeout = timeout
        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

    def get_metadata(self) -> Metadata:
        return Metadata(name="OpenFeature Remote Evaluation Protocol Provider")

    def get_provider_hooks(self) -> List[Hook]:
        return []

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(flag_key, default_value, evaluation_context)

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve(flag_key, default_value, evaluation_context)

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return self._resolve(flag_key, default_value, evaluation_context)

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return self._resolve(flag_key, default_value, evaluation_context)

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        return self._resolve(flag_key, default_value, evaluation_context)

    def _resolve(
        self,
        flag_key: str,
        default_value: Union[bool, str, int, float, dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Any]:
        try:
            response = self.session.post(
                urljoin(self.base_url, f"/ofrep/v1/evaluate/flags/{flag_key}"),
                json=_build_request_data(evaluation_context),
                timeout=self.timeout,
            )
            response.raise_for_status()

        except requests.RequestException as e:
            if e.response is None:
                raise GeneralError(str(e)) from e

            try:
                data = e.response.json()
            except JSONDecodeError:
                raise ParseError(str(e)) from e

            if e.response.status_code == 404:
                raise FlagNotFoundError(data["errorDetails"]) from e

            error_code = ErrorCode(data["errorCode"])
            error_details = data["errorDetails"]

            if error_code == ErrorCode.PARSE_ERROR:
                raise ParseError(error_details) from e
            if error_code == ErrorCode.TARGETING_KEY_MISSING:
                raise TargetingKeyMissingError(error_details) from e
            if error_code == ErrorCode.INVALID_CONTEXT:
                raise InvalidContextError(error_details) from e
            if error_code == ErrorCode.GENERAL:
                raise GeneralError(error_details) from e

            raise OpenFeatureError(error_code, error_details) from e

        try:
            data = response.json()
        except JSONDecodeError as e:
            raise ParseError(str(e)) from e

        return FlagResolutionDetails(
            value=data["value"],
            reason=Reason[data["reason"]],
            variant=data["variant"],
            flag_metadata=data["metadata"],
        )


def _build_request_data(
    evaluation_context: Optional[EvaluationContext],
) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if evaluation_context:
        data["context"] = {}
        if evaluation_context.targeting_key:
            data["context"]["targetingKey"] = evaluation_context.targeting_key
        data["context"].update(evaluation_context.attributes)
    return data
