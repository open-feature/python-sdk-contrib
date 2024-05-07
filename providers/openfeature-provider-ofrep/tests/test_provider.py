import pytest

from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason


def test_provider_init():
    OFREPProvider("http://localhost:8080", headers={"Authorization": "Bearer token"})


def test_provider_successful_resolution(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        json={
            "key": "flag_key",
            "reason": "TARGETING_MATCH",
            "variant": "true",
            "metadata": {"foo": "bar"},
            "value": True,
        },
    )

    resolution = ofrep_provider.resolve_boolean_details("flag_key", False)

    assert resolution == FlagResolutionDetails(
        value=True,
        reason=Reason.TARGETING_MATCH,
        variant="true",
        flag_metadata={"foo": "bar"},
    )


def test_provider_flag_not_found(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=404,
        json={
            "key": "flag_key",
            "errorCode": "FLAG_NOT_FOUND",
            "errorDetails": "Flag 'flag_key' not found",
        },
    )

    with pytest.raises(FlagNotFoundError):
        ofrep_provider.resolve_boolean_details("flag_key", False)


def test_provider_invalid_context(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=400,
        json={
            "key": "flag_key",
            "errorCode": "INVALID_CONTEXT",
            "errorDetails": "Invalid context provided",
        },
    )

    with pytest.raises(InvalidContextError):
        ofrep_provider.resolve_boolean_details("flag_key", False)


def test_provider_invalid_response(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key", text="invalid"
    )

    with pytest.raises(ParseError):
        ofrep_provider.resolve_boolean_details("flag_key", False)


def test_provider_evaluation_context(ofrep_provider, requests_mock):
    def match_request_json(request):
        return request.json() == {"context": {"targetingKey": "1", "foo": "bar"}}

    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        json={
            "key": "flag_key",
            "reason": "TARGETING_MATCH",
            "variant": "true",
            "metadata": {},
            "value": True,
        },
        additional_matcher=match_request_json,
    )

    context = EvaluationContext("1", {"foo": "bar"})
    resolution = ofrep_provider.resolve_boolean_details(
        "flag_key", False, evaluation_context=context
    )

    assert resolution == FlagResolutionDetails(
        value=True,
        reason=Reason.TARGETING_MATCH,
        variant="true",
    )


def test_provider_retry_after_shortcircuit_resolution(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=429,
        headers={"Retry-After": "1"},
    )

    with pytest.raises(GeneralError, match="Rate limited, retry after: 1"):
        ofrep_provider.resolve_boolean_details("flag_key", False)
    with pytest.raises(
        GeneralError, match="OFREP evaluation paused due to TooManyRequests"
    ):
        ofrep_provider.resolve_boolean_details("flag_key", False)
