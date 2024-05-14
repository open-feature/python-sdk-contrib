import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, List, NoReturn, Optional, Tuple, Type, Union
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
from openfeature.flag_evaluation import FlagResolutionDetails, FlagType, Reason
from openfeature.hook import Hook
from openfeature.provider import AbstractProvider, Metadata

__all__ = ["OFREPProvider"]


TypeMap = Dict[
    FlagType,
    Union[
        Type[bool],
        Type[int],
        Type[float],
        Type[str],
        Tuple[Type[dict], Type[list]],
    ],
]


class OFREPProvider(AbstractProvider):
    def __init__(
        self,
        base_url: str,
        *,
        headers_factory: Optional[Callable[[], Dict[str, str]]] = None,
        timeout: float = 5.0,
    ):
        self.base_url = base_url
        self.headers_factory = headers_factory
        self.timeout = timeout
        self.retry_after: Optional[datetime] = None
        self.session = requests.Session()

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
        default_value: Union[dict, list],
        evaluation_context: Optional[EvaluationContext] = None,
    ) -> FlagResolutionDetails[Union[dict, list]]:
        return self._resolve(
            FlagType.OBJECT, flag_key, default_value, evaluation_context
        )

    def _resolve(
        self,
        flag_type: FlagType,
        flag_key: str,
        default_value: Union[bool, str, int, float, dict, list],
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
                urljoin(self.base_url, f"/ofrep/v1/evaluate/flags/{flag_key}"),
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
            flag_metadata=data["metadata"],
        )

    def _handle_error(self, exception: requests.RequestException) -> NoReturn:
        response = exception.response
        if response is None:
            raise GeneralError(str(exception)) from exception

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            self.retry_after = _parse_retry_after(retry_after)
            raise GeneralError(
                f"Rate limited, retry after: {retry_after}"
            ) from exception

        try:
            data = response.json()
        except JSONDecodeError:
            raise ParseError(str(exception)) from exception

        error_code = ErrorCode(data["errorCode"])
        error_details = data["errorDetails"]

        if response.status_code == 404:
            raise FlagNotFoundError(error_details) from exception

        if error_code == ErrorCode.PARSE_ERROR:
            raise ParseError(error_details) from exception
        if error_code == ErrorCode.TARGETING_KEY_MISSING:
            raise TargetingKeyMissingError(error_details) from exception
        if error_code == ErrorCode.INVALID_CONTEXT:
            raise InvalidContextError(error_details) from exception
        if error_code == ErrorCode.GENERAL:
            raise GeneralError(error_details) from exception

        raise OpenFeatureError(error_code, error_details) from exception


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
