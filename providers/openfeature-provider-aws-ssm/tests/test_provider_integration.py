import pytest
from botocore.config import Config

from openfeature.contrib.provider.awsssm import AwsSsmProvider, AwsSsmProviderConfig
from openfeature.exception import ParseError, TypeMismatchError
from openfeature.flag_evaluation import Reason


@pytest.mark.parametrize(
    ("resolve_method", "flag_key", "ssm_value", "expected_value"),
    [
        ("resolve_string_details", "/test-string", "hello-world", "hello-world"),
        ("resolve_boolean_details", "/test-bool-true", "true", True),
        ("resolve_boolean_details", "/test-bool-false", "false", False),
        ("resolve_integer_details", "/test-int-pos", "42", 42),
        ("resolve_integer_details", "/test-int-neg", "-123", -123),
        ("resolve_float_details", "/test-float-pos", "3.14", 3.14),
        ("resolve_float_details", "/test-float-neg", "-2.5", -2.5),
        (
            "resolve_object_details",
            "/test-object-dict",
            '{"key": "value", "number": 42}',
            {"key": "value", "number": 42},
        ),
        (
            "resolve_object_details",
            "/test-object-list",
            '[1, 2, 3, "four"]',
            [1, 2, 3, "four"],
        ),
    ],
)
def test_flag_resolution(
    provider, ssm_client, resolve_method, flag_key, ssm_value, expected_value
):
    ssm_client.put_parameter(Name=flag_key, Value=ssm_value, Type="String")

    resolve_func = getattr(provider, resolve_method)
    result = resolve_func(flag_key, None, None)

    assert result.value == expected_value
    assert result.reason == Reason.STATIC


@pytest.mark.parametrize(
    (
        "resolve_method",
        "flag_key",
        "invalid_value",
        "default_value",
        "expected_exception",
    ),
    [
        ("resolve_boolean_details", "/invalid-bool", "yes", False, TypeMismatchError),
        (
            "resolve_integer_details",
            "/invalid-int",
            "not-a-number",
            0,
            TypeMismatchError,
        ),
        (
            "resolve_float_details",
            "/invalid-float",
            "not-a-float",
            0.0,
            TypeMismatchError,
        ),
        ("resolve_object_details", "/invalid-json", "not-valid-json", {}, ParseError),
        ("resolve_object_details", "/non-object-json", "42", {}, ParseError),
    ],
)
def test_invalid_flag_values(  # noqa: PLR0913
    provider,
    ssm_client,
    resolve_method,
    flag_key,
    invalid_value,
    default_value,
    expected_exception,
):
    ssm_client.put_parameter(Name=flag_key, Value=invalid_value, Type="String")

    resolve_func = getattr(provider, resolve_method)
    with pytest.raises(expected_exception):
        resolve_func(flag_key, default_value, None)


def test_flag_key_normalization_adds_leading_slash(provider, ssm_client):
    ssm_client.put_parameter(Name="/my-flag", Value="test", Type="String")

    result = provider.resolve_string_details("my-flag", "default", None)

    assert result.value == "test"


def test_flag_key_with_path(provider, ssm_client):
    ssm_client.put_parameter(
        Name="/app/prod/feature-flag", Value="enabled", Type="String"
    )

    result = provider.resolve_string_details("/app/prod/feature-flag", "default", None)

    assert result.value == "enabled"


@pytest.mark.parametrize(
    ("param_name", "param_value"),
    [
        ("/app/prod/feature-flag", "prod-value"),
        ("/app/dev/feature-flag", "dev-value"),
        ("/service/api/rate-limit", "100"),
        ("/config/database/connection-string", "postgres://localhost"),
        ("/feature/experimental/new-ui", "true"),
    ],
)
def test_flag_key_hierarchical_paths_with_leading_slash(
    provider, ssm_client, param_name, param_value
):
    ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String")
    result = provider.resolve_string_details(param_name, "default", None)
    assert result.value == param_value
    assert result.reason == Reason.STATIC


@pytest.mark.parametrize(
    ("param_name", "param_value"),
    [
        ("app/prod/feature-flag", "prod-value"),
        ("app/dev/feature-flag", "dev-value"),
        ("service/api/rate-limit", "100"),
        ("config/database/url", "postgres://localhost"),
    ],
)
def test_flag_key_hierarchical_paths_without_leading_slash(
    provider, ssm_client, param_name, param_value
):
    ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String")
    result = provider.resolve_string_details(param_name, "default", None)
    assert result.value == param_value
    assert result.reason == Reason.STATIC


@pytest.mark.parametrize(
    ("param_name", "param_value"),
    [
        ("/organization/team/project/environment/feature", "value1"),
        ("/a/b/c/d/e/f/g", "deep-value"),
        ("/apps/microservices/auth/v2/jwt/secret", "secret-key"),
    ],
)
def test_flag_key_deeply_nested_paths(provider, ssm_client, param_name, param_value):
    ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String")
    result = provider.resolve_string_details(param_name, "default", None)
    assert result.value == param_value


@pytest.mark.parametrize(
    ("param_name", "param_value"),
    [
        ("/feature-flags/new_ui", "enabled"),
        ("/api.v2/rate-limit", "1000"),
        ("/service_name/config-value", "test"),
        ("/app/feature.flag.name", "value"),
        ("/kebab-case/snake_case/dot.case", "mixed"),
    ],
)
def test_flag_key_with_special_characters_in_path(
    provider, ssm_client, param_name, param_value
):
    ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String")
    result = provider.resolve_string_details(param_name, "default", None)
    assert result.value == param_value


@pytest.mark.parametrize(
    ("param_name", "param_value"),
    [
        ("/api/v1/timeout", "30"),
        ("/api/v2/timeout", "60"),
        ("/service123/config", "value"),
        ("/app/feature-123", "enabled"),
        ("/v1.2.3/config", "versioned"),
    ],
)
def test_flag_key_with_numbers_in_path(provider, ssm_client, param_name, param_value):
    ssm_client.put_parameter(Name=param_name, Value=param_value, Type="String")
    result = provider.resolve_string_details(param_name, "default", None)
    assert result.value == param_value


def test_multiple_flags_same_prefix(provider, ssm_client):
    # Set up multiple parameters with common prefix
    ssm_client.put_parameter(Name="/app/prod/flag1", Value="value1", Type="String")
    ssm_client.put_parameter(Name="/app/prod/flag2", Value="value2", Type="String")
    ssm_client.put_parameter(Name="/app/prod/flag3", Value="value3", Type="String")
    ssm_client.put_parameter(Name="/app/dev/flag1", Value="dev-value1", Type="String")

    # Verify each can be resolved independently
    result1 = provider.resolve_string_details("/app/prod/flag1", "default", None)
    assert result1.value == "value1"

    result2 = provider.resolve_string_details("/app/prod/flag2", "default", None)
    assert result2.value == "value2"

    result3 = provider.resolve_string_details("/app/prod/flag3", "default", None)
    assert result3.value == "value3"

    result4 = provider.resolve_string_details("/app/dev/flag1", "default", None)
    assert result4.value == "dev-value1"


def test_flag_types_with_hierarchical_paths(provider, ssm_client):
    ssm_client.put_parameter(
        Name="/config/feature/enabled", Value="true", Type="String"
    )
    ssm_client.put_parameter(Name="/config/api/timeout", Value="30", Type="String")
    ssm_client.put_parameter(Name="/config/api/rate", Value="99.5", Type="String")
    ssm_client.put_parameter(
        Name="/config/api/settings", Value='{"key": "value"}', Type="String"
    )

    # Boolean
    bool_result = provider.resolve_boolean_details(
        "/config/feature/enabled", False, None
    )
    assert bool_result.value is True

    # Integer
    int_result = provider.resolve_integer_details("/config/api/timeout", 0, None)
    assert int_result.value == 30

    # Float
    float_result = provider.resolve_float_details("/config/api/rate", 0.0, None)
    assert float_result.value == 99.5

    # Object
    obj_result = provider.resolve_object_details("/config/api/settings", {}, None)
    assert obj_result.value == {"key": "value"}


@pytest.mark.asyncio
async def test_async_with_hierarchical_paths(ssm_client):
    config = AwsSsmProviderConfig(config=Config(region_name="us-east-1"))
    provider = AwsSsmProvider(config=config)

    ssm_client.put_parameter(
        Name="/app/async/feature", Value="async-value", Type="String"
    )

    result = await provider.resolve_string_details_async(
        "/app/async/feature", "default", None
    )

    assert result.value == "async-value"
    assert result.reason == Reason.STATIC


def test_secure_string_decryption_disabled(ssm_client):
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"), enable_decryption=False
    )
    provider = AwsSsmProvider(config=config)

    ssm_client.put_parameter(
        Name="/secure-param", Value="secret-value", Type="SecureString"
    )

    # With decryption disabled, moto returns the encrypted value
    result = provider.resolve_string_details("secure-param", "default", None)
    # Moto encrypts with a prefix, just check it's not the raw value
    assert result.value != "secret-value" or result.value.startswith("kms:")


def test_secure_string_decryption_enabled(ssm_client):
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"), enable_decryption=True
    )
    provider = AwsSsmProvider(config=config)

    ssm_client.put_parameter(
        Name="/secure-param", Value="secret-value", Type="SecureString"
    )

    result = provider.resolve_string_details("secure-param", "default", None)
    # With decryption enabled, should get the plain value
    assert result.value == "secret-value"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("resolve_method", "flag_key", "ssm_value", "expected_value", "default_value"),
    [
        (
            "resolve_string_details_async",
            "/async-string",
            "async-value",
            "async-value",
            "default",
        ),
        ("resolve_boolean_details_async", "/async-bool", "true", True, False),
        ("resolve_integer_details_async", "/async-int", "99", 99, 0),
        ("resolve_float_details_async", "/async-float", "1.5", 1.5, 0.0),
        (
            "resolve_object_details_async",
            "/async-object",
            '{"async": true}',
            {"async": True},
            {},
        ),
    ],
)
async def test_async_flag_resolution(
    ssm_client, resolve_method, flag_key, ssm_value, expected_value, default_value
):
    config = AwsSsmProviderConfig(config=Config(region_name="us-east-1"))
    provider = AwsSsmProvider(config=config)

    ssm_client.put_parameter(Name=flag_key, Value=ssm_value, Type="String")

    resolve_func = getattr(provider, resolve_method)
    result = await resolve_func(flag_key, default_value, None)

    assert result.value == expected_value
    assert result.reason == Reason.STATIC
