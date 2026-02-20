import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, NoReturn, Optional, Union
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
    TypeMismatchError,
)
from openfeature.flag_evaluation import (
    FlagResolutionDetails,
    FlagType,
    FlagValueType,
    Reason,
)
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata

__all__ = ["OFREPProvider"]


TypeMap = dict[
    FlagType,
    Union[
        type[bool],
        type[int],
        type[float],
        type[str],
        tuple[type[dict], type[list]],
    ],
]

_HTTP_AUTH_ERRORS: dict[int, str] = {401: "unauthorized", 403: "forbidden"}


class OFREPProvider(AbstractProvider):
    def __init__(
        self,
        base_url: str,
        *,
        headers_factory: Optional[Callable[[], dict[str, str]]] = None,
        timeout: float = 5.0,
    ):
        self.base_url = base_url
        self.headers_factory = headers_factory
        self.timeout = timeout
        self.retry_after: Optional[datetime] = None
        self.session = requests.Session()

    def get_metadata(self) -> Metadata:
        return Metadata(name="OpenFeature Remote Evaluation Protocol Provider")

    def get_provider_hooks(self) -> list[Hook]:
        return []

    def resolve_boolean_details(
        self,
        flag_key: str,
        default_value: bool,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[bool]:
        return self._resolve(
            FlagType.BOOLEAN, flag_key, default_value, evaluation_context
        )

    def resolve_string_details(
        self,
        flag_key: str,
        default_value: str,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[str]:
        return self._resolve(
            FlagType.STRING, flag_key, default_value, evaluation_context
        )

    def resolve_integer_details(
        self,
        flag_key: str,
        default_value: int,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[int]:
        return self._resolve(
            FlagType.INTEGER, flag_key, default_value, evaluation_context
        )

    def resolve_float_details(
        self,
        flag_key: str,
        default_value: float,
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[float]:
        return self._resolve(
            FlagType.FLOAT, flag_key, default_value, evaluation_context
        )

    def resolve_object_details(
        self,
        flag_key: str,
        default_value: Union[Sequence[FlagValueType], Mapping[str, FlagValueType]],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[
        Union[Sequence[FlagValueType], Mapping[str, FlagValueType]]
    ]:
        return self._resolve(
            FlagType.OBJECT, flag_key, default_value, evaluation_context
        )

    def _get_ofrep_api_url(self, api_version: str = "v1") -> str:
        ofrep_base_url = (
            self.base_url if self.base_url.endswith("/") else f"{self.base_url}/"
        )
        return urljoin(ofrep_base_url, f"ofrep/{api_version}/")

    def _resolve(
        self,
        flag_type: FlagType,
        flag_key: str,
        default_value: Union[
            bool,
            str,
            int,
            float,
            dict,
            list,
            Sequence[FlagValueType],
            Mapping[str, FlagValueType],
        ],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Any]:
        now = datetime.now(timezone.utc)
        if self.retry_after and now <= self.retry_after:
            raise GeneralError(
                f"OFREP evaluation paused due to TooManyRequests until {self.retry_after}"
            )
        elif self.retry_after:
            self.retry_after = None

        try:
            response = self.session.post(
                urljoin(self._get_ofrep_api_url(), f"evaluate/flags/{flag_key}"),
                json=_build_request_data(evaluation_context),
                timeout=self.timeout,
                headers=self.headers_factory() if self.headers_factory else None,
            )
            response.raise_for_status()

        except requests.RequestException as e:
            self._handle_error(e)

        try:
            data = response.json()
        except JSONDecodeError as e:
            raise ParseError(str(e)) from e

        _typecheck_flag_value(data["value"], flag_type)

        return FlagResolutionDetails(
            value=data["value"],
            reason=Reason[data["reason"]],
            variant=data["variant"],
            flag_metadata=data.get("metadata", {}),
        )

    def _handle_error(self, exception: requests.RequestException) -> NoReturn:
        response = exception.response
        if response is None:
            raise GeneralError(str(exception)) from exception

        self._raise_for_http_status(response, exception)
        # Fallthrough: parse JSON and raise based on error code
        try:
            data = response.json()
        except JSONDecodeError:
            raise ParseError(str(exception)) from exception

        error_code = ErrorCode(data.get("errorCode", "GENERAL"))
        error_details = data["errorDetails"]

        if error_code == ErrorCode.PARSE_ERROR:
            raise ParseError(error_details) from exception
        if error_code == ErrorCode.TARGETING_KEY_MISSING:
            raise TargetingKeyMissingError(error_details) from exception
        if error_code == ErrorCode.INVALID_CONTEXT:
            raise InvalidContextError(error_details) from exception
        if error_code == ErrorCode.GENERAL:
            raise GeneralError(error_details) from exception

        raise OpenFeatureError(error_code, error_details) from exception

    def _raise_for_http_status(
        self,
        response: requests.Response,
        exception: requests.RequestException,
    ) -> None:
        status = response.status_code

        if status == 429:
            retry_after = response.headers.get("Retry-After")
            self.retry_after = _parse_retry_after(retry_after)
            raise GeneralError(
                f"Rate limited, retry after: {retry_after}"
            ) from exception
        elif status in _HTTP_AUTH_ERRORS:
            raise OpenFeatureError(
                ErrorCode.GENERAL, _HTTP_AUTH_ERRORS[status]
            ) from exception
        elif status == 404:
            try:
                error_details = response.json()["errorDetails"]
            except (JSONDecodeError, KeyError):
                error_details = response.text
            raise FlagNotFoundError(error_details) from exception
        elif status > 400:
            raise OpenFeatureError(ErrorCode.GENERAL, response.text) from exception


def _build_request_data(
    evaluation_context: Optional[EvaluationContext],
) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if evaluation_context:
        data["context"] = {}
        if evaluation_context.targeting_key:
            data["context"]["targetingKey"] = evaluation_context.targeting_key
        data["context"].update(evaluation_context.attributes)
    return data


def _parse_retry_after(retry_after: Optional[str]) -> Optional[datetime]:
    if retry_after is None:
        return None
    if re.match(r"^\s*[0-9]+\s*$", retry_after):
        seconds = int(retry_after)
        return datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return parsedate_to_datetime(retry_after)


def _typecheck_flag_value(value: Any, flag_type: FlagType) -> None:
    type_map: TypeMap = {
        FlagType.BOOLEAN: bool,
        FlagType.STRING: str,
        FlagType.OBJECT: (dict, list),
        FlagType.FLOAT: float,
        FlagType.INTEGER: int,
    }
    _type = type_map.get(flag_type)
    if not _type:
        raise GeneralError(error_message="Unknown flag type")
    if not isinstance(value, _type):
        raise TypeMismatchError(f"Expected type {_type} but got {type(value)}")
