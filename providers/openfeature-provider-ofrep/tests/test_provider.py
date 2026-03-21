import pytest

from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    ErrorCode,
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    OpenFeatureError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason


def test_provider_init():
    OFREPProvider(
        "http://localhost:8080",
        headers_factory=lambda: {"Authorization": "Bearer token"},
    )


@pytest.mark.parametrize(
    "flag_type, resolved_value, default_value, get_method",
    (
        (bool, True, False, "resolve_boolean_details"),
        (str, "String", "default", "resolve_string_details"),
        (int, 100, 0, "resolve_integer_details"),
        (float, 10.23, 0.0, "resolve_float_details"),
        (
            dict,
            {
                "String": "string",
                "Number": 2,
                "Boolean": True,
            },
            {},
            "resolve_object_details",
        ),
        (
            list,
            ["string1", "string2"],
            [],
            "resolve_object_details",
        ),
    ),
)
def test_provider_successful_resolution(
    flag_type, resolved_value, default_value, get_method, ofrep_provider, requests_mock
):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        json={
            "key": "flag_key",
            "reason": "TARGETING_MATCH",
            "variant": str(resolved_value),
            "metadata": {"foo": "bar"},
            "value": resolved_value,
        },
    )

    resolution = getattr(ofrep_provider, get_method)("flag_key", default_value)

    assert resolution == FlagResolutionDetails(
        value=resolved_value,
        reason=Reason.TARGETING_MATCH,
        variant=str(resolved_value),
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


def test_provider_unauthorized(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=401,
        text="unauthorized",
    )

    with pytest.raises(OpenFeatureError) as exc_info:
        ofrep_provider.resolve_boolean_details("flag_key", False)

    assert exc_info.value.error_code == ErrorCode.GENERAL
    assert exc_info.value.error_message == "unauthorized"


def test_provider_forbidden(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=403,
        text="forbidden",
    )

    with pytest.raises(OpenFeatureError) as exc_info:
        ofrep_provider.resolve_boolean_details("flag_key", False)

    assert exc_info.value.error_code == ErrorCode.GENERAL
    assert exc_info.value.error_message == "forbidden"


def test_provider_flag_not_found_invalid_json(ofrep_provider, requests_mock):
    """Test 404 with non-JSON response falls back to response text for error details"""
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=404,
        text="Flag not found - plain text response",
    )

    with pytest.raises(FlagNotFoundError, match="Flag not found - plain text response"):
        ofrep_provider.resolve_boolean_details("flag_key", False)


def test_provider_server_error(ofrep_provider, requests_mock):
    """Test generic OpenFeatureError for status codes > 400 (e.g. 500, 502)"""
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=500,
        text="Internal Server Error",
    )

    with pytest.raises(OpenFeatureError) as exc_info:
        ofrep_provider.resolve_boolean_details("flag_key", False)

    assert exc_info.value.error_code == ErrorCode.GENERAL
    assert exc_info.value.error_message == "Internal Server Error"


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


def test_provider_typecheck_flag_value(ofrep_provider, requests_mock):
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        json={
            "key": "flag_key",
            "reason": "TARGETING_MATCH",
            "variant": "true",
            "metadata": {},
            "value": "true",
        },
    )

    with pytest.raises(TypeMismatchError):
        ofrep_provider.resolve_boolean_details("flag_key", False)


def test_provider_missing_metadata_field(ofrep_provider, requests_mock):
    """Test that provider handles missing metadata field gracefully"""
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        json={
            "key": "flag_key",
            "reason": "TARGETING_MATCH",
            "variant": "true",
            "value": True,
        },
    )

    resolution = ofrep_provider.resolve_boolean_details("flag_key", False)

    assert resolution == FlagResolutionDetails(
        value=True,
        reason=Reason.TARGETING_MATCH,
        variant="true",
        flag_metadata={},
    )


@pytest.mark.parametrize(
    "base_url",
    [
        "https://localhost:8080",
        "https://localhost:8080/",
        "https://localhost:8080/tools/feature_flags",
        "https://localhost:8080/tools/feature_flags/",
    ],
)
def test_provider_api_path_resolution(base_url):
    provider = OFREPProvider(base_url=base_url)
    assert provider._get_ofrep_api_url() == f"{base_url.rstrip('/')}/ofrep/v1/"
