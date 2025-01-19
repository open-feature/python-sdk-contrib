import pytest

from openfeature.contrib.provider.flipt import FliptProvider
from openfeature.evaluation_context import EvaluationContext
from openfeature.exception import (
    FlagNotFoundError,
    GeneralError,
    InvalidContextError,
    ParseError,
    TypeMismatchError,
)
from openfeature.flag_evaluation import FlagResolutionDetails, Reason


@pytest.mark.parametrize(
    "headers_factory_fixture", [None, lambda: {"Authorization": "Bearer token"}]
)
def test_flipt_provider_init(headers_factory_fixture):
    """Test that the FliptProvider correctly initializes and merges the headers factory with the namespace header"""
    provider = FliptProvider(
        "http://localhost:8080",
        "test-namespace",
        headers_factory=headers_factory_fixture,
    )
    assert provider.base_url == "http://localhost:8080"
    if headers_factory_fixture:
        assert provider.headers_factory() == {
            **headers_factory_fixture(),
            "X-Flipt-Namespace": "test-namespace",
        }
    else:
        assert provider.headers_factory() == {
            "X-Flipt-Namespace": "test-namespace",
        }


@pytest.mark.parametrize(
    "get_method, resolved_value, default_value",
    (
        ("resolve_boolean_details", True, False),
        ("resolve_string_details", "resolved_flag_str", "default_flag_str"),
        ("resolve_integer_details", 100, 0),
        ("resolve_float_details", 10.23, 0.0),
        (
            "resolve_object_details",
            {
                "String": "string",
                "Number": 2,
                "Boolean": True,
            },
            {},
        ),
        ("resolve_object_details", ["string1", "string2"], []),
    ),
)
def test_flipt_provider_successful_resolution(
    get_method, resolved_value, default_value, requests_mock
):
    """Mock any call to Flipt OFREP api and validat that the resolution function for each type returns the expected FlagResolutionDetails"""

    provider = FliptProvider("http://localhost:8080", "test-namespace")
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

    resolution = getattr(provider, get_method)("flag_key", default_value)

    assert resolution == FlagResolutionDetails(
        value=resolved_value,
        reason=Reason.TARGETING_MATCH,
        variant=str(resolved_value),
        flag_metadata={"foo": "bar"},
    )


def test_flipt_provider_flag_not_found(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")
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
        provider.resolve_boolean_details("flag_key", False)


def test_flipt_provider_invalid_context(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")
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
        provider.resolve_boolean_details("flag_key", False)


def test_flipt_provider_invalid_response(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key", text="invalid"
    )

    with pytest.raises(ParseError):
        provider.resolve_boolean_details("flag_key", False)


def test_flipt_provider_evaluation_context(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")

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
    resolution = provider.resolve_boolean_details(
        "flag_key", False, evaluation_context=context
    )

    assert resolution == FlagResolutionDetails(
        value=True,
        reason=Reason.TARGETING_MATCH,
        variant="true",
    )


def test_flipt_provider_retry_after_shortcircuit_resolution(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")
    requests_mock.post(
        "http://localhost:8080/ofrep/v1/evaluate/flags/flag_key",
        status_code=429,
        headers={"Retry-After": "1"},
    )

    with pytest.raises(GeneralError, match="Rate limited, retry after: 1"):
        provider.resolve_boolean_details("flag_key", False)
    with pytest.raises(
        GeneralError, match="OFREP evaluation paused due to TooManyRequests"
    ):
        provider.resolve_boolean_details("flag_key", False)


def test_flipt_provider_typecheck_flag_value(requests_mock):
    provider = FliptProvider("http://localhost:8080", "test-namespace")
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
        provider.resolve_boolean_details("flag_key", False)
