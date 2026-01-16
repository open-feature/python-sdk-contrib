"""Unit tests for ssm_service module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.config import Config
from botocore.exceptions import ClientError

from openfeature.contrib.provider.awsssm.ssm_service import SsmService
from openfeature.exception import FlagNotFoundError, GeneralError


class TestHandleClientError:
    """Tests for _handle_client_error method."""

    def test_handle_parameter_not_found_error(self):
        """Test that ParameterNotFound raises FlagNotFoundError."""
        service = SsmService()
        error = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Parameter not found"}},
            "GetParameter",
        )

        with pytest.raises(FlagNotFoundError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "Parameter '/test-param' not found" in str(exc_info.value)

    def test_handle_access_denied_exception(self):
        """Test that AccessDeniedException raises GeneralError."""
        service = SsmService()
        error = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}},
            "GetParameter",
        )

        with pytest.raises(GeneralError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "Access denied to parameter '/test-param'" in str(exc_info.value)

    def test_handle_access_denied_error(self):
        """Test that AccessDenied raises GeneralError."""
        service = SsmService()
        error = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "GetParameter",
        )

        with pytest.raises(GeneralError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "Access denied to parameter '/test-param'" in str(exc_info.value)

    def test_handle_throttling_exception(self):
        """Test that ThrottlingException raises GeneralError."""
        service = SsmService()
        error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "GetParameter",
        )

        with pytest.raises(GeneralError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "Throttled while accessing parameter '/test-param'" in str(
            exc_info.value
        )

    def test_handle_too_many_requests_exception(self):
        """Test that TooManyRequestsException raises GeneralError."""
        service = SsmService()
        error = ClientError(
            {
                "Error": {
                    "Code": "TooManyRequestsException",
                    "Message": "Too many requests",
                }
            },
            "GetParameter",
        )

        with pytest.raises(GeneralError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "Throttled while accessing parameter '/test-param'" in str(
            exc_info.value
        )

    def test_handle_unknown_error(self):
        """Test that unknown ClientError raises GeneralError."""
        service = SsmService()
        error = ClientError(
            {"Error": {"Code": "UnknownError", "Message": "Something went wrong"}},
            "GetParameter",
        )

        with pytest.raises(GeneralError) as exc_info:
            service._handle_client_error(error, "/test-param")
        assert "AWS SSM error" in str(exc_info.value)


class TestGetParameterValue:
    """Tests for get_parameter_value method."""

    @patch("boto3.client")
    def test_get_parameter_value_success(self, mock_boto_client):
        """Test successful parameter value retrieval."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "test-value"}}

        service = SsmService()
        result = service.get_parameter_value("my-flag")

        assert result == "test-value"
        mock_client.get_parameter.assert_called_once_with(
            Name="my-flag", WithDecryption=False
        )

    @patch("boto3.client")
    def test_get_parameter_value_with_decryption_enabled(self, mock_boto_client):
        """Test parameter retrieval with decryption enabled."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.return_value = {
            "Parameter": {"Value": "decrypted-value"}
        }

        service = SsmService(enable_decryption=True)
        result = service.get_parameter_value("secure-flag")

        assert result == "decrypted-value"
        mock_client.get_parameter.assert_called_once_with(
            Name="secure-flag", WithDecryption=True
        )

    @patch("boto3.client")
    def test_get_parameter_value_with_decryption_disabled(self, mock_boto_client):
        """Test parameter retrieval with decryption explicitly disabled."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}

        service = SsmService(enable_decryption=False)
        result = service.get_parameter_value("flag")

        assert result == "value"
        mock_client.get_parameter.assert_called_once_with(
            Name="flag", WithDecryption=False
        )

    @patch("boto3.client")
    def test_get_parameter_value_not_found(self, mock_boto_client):
        """Test that missing parameter raises FlagNotFoundError."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
            "GetParameter",
        )

        service = SsmService()
        with pytest.raises(FlagNotFoundError):
            service.get_parameter_value("missing-flag")

    @patch("boto3.client")
    def test_get_parameter_value_with_leading_slash(self, mock_boto_client):
        """Test that flags with leading slash are passed as-is."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}

        service = SsmService()
        result = service.get_parameter_value("/already-has-slash")

        assert result == "value"
        mock_client.get_parameter.assert_called_once_with(
            Name="/already-has-slash", WithDecryption=False
        )


class TestGetParameterValueAsync:
    """Tests for get_parameter_value_async method."""

    @pytest.mark.asyncio
    @patch("openfeature.contrib.provider.awsssm.ssm_service.aioboto3")
    async def test_get_parameter_value_async_success(self, mock_aioboto3):
        """Test successful async parameter value retrieval."""
        # Setup mock async client
        mock_session = MagicMock()
        mock_aioboto3.Session.return_value = mock_session

        mock_client = MagicMock()
        mock_client.get_parameter = AsyncMock(
            return_value={"Parameter": {"Value": "async-value"}}
        )

        # Create async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_session.client.return_value = mock_context

        service = SsmService()
        result = await service.get_parameter_value_async("async-flag")

        assert result == "async-value"
        mock_client.get_parameter.assert_called_once_with(
            Name="async-flag", WithDecryption=False
        )

    @pytest.mark.asyncio
    @patch("openfeature.contrib.provider.awsssm.ssm_service.aioboto3", None)
    async def test_get_parameter_value_async_missing_aioboto3(self):
        """Test that missing aioboto3 raises ImportError."""
        service = SsmService()

        with pytest.raises(ImportError) as exc_info:
            await service.get_parameter_value_async("flag")

        assert "aioboto3 is required for async support" in str(exc_info.value)
        assert "pip install openfeature-provider-aws-ssm[async]" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("openfeature.contrib.provider.awsssm.ssm_service.aioboto3")
    async def test_get_parameter_value_async_with_decryption(self, mock_aioboto3):
        """Test async parameter retrieval with decryption enabled."""
        mock_session = MagicMock()
        mock_aioboto3.Session.return_value = mock_session

        mock_client = MagicMock()
        mock_client.get_parameter = AsyncMock(
            return_value={"Parameter": {"Value": "encrypted-value"}}
        )

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_session.client.return_value = mock_context

        service = SsmService(enable_decryption=True)
        result = await service.get_parameter_value_async("secure-flag")

        assert result == "encrypted-value"
        mock_client.get_parameter.assert_called_once_with(
            Name="secure-flag", WithDecryption=True
        )

    @pytest.mark.asyncio
    @patch("openfeature.contrib.provider.awsssm.ssm_service.aioboto3")
    async def test_get_parameter_value_async_not_found(self, mock_aioboto3):
        """Test that async missing parameter raises FlagNotFoundError."""
        mock_session = MagicMock()
        mock_aioboto3.Session.return_value = mock_session

        mock_client = MagicMock()
        mock_client.get_parameter = AsyncMock(
            side_effect=ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": "Not found"}},
                "GetParameter",
            )
        )

        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_client
        mock_session.client.return_value = mock_context

        service = SsmService()
        with pytest.raises(FlagNotFoundError):
            await service.get_parameter_value_async("missing-flag")


class TestServiceInitialization:
    """Tests for SsmService initialization."""

    @patch("boto3.client")
    def test_initialization_with_custom_config(self, mock_boto_client):
        """Test service initialization with custom boto3 Config."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        custom_config = Config(region_name="us-west-2", retries={"max_attempts": 5})
        service = SsmService(config=custom_config)

        # Trigger client creation
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}
        service.get_parameter_value("test")

        # Verify config was passed to client
        mock_boto_client.assert_called_once_with("ssm", config=custom_config)

    @patch("boto3.client")
    def test_initialization_with_endpoint_url(self, mock_boto_client):
        """Test service initialization with custom endpoint URL."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        service = SsmService(endpoint_url="http://localhost:4566")

        # Trigger client creation
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}
        service.get_parameter_value("test")

        # Verify endpoint_url was passed to client
        mock_boto_client.assert_called_once_with(
            "ssm", endpoint_url="http://localhost:4566"
        )

    @patch("boto3.client")
    def test_initialization_with_config_and_endpoint(self, mock_boto_client):
        """Test service initialization with both config and endpoint URL."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        custom_config = Config(region_name="eu-west-1")
        service = SsmService(config=custom_config, endpoint_url="http://localhost:4566")

        # Trigger client creation
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}
        service.get_parameter_value("test")

        # Verify both were passed to client
        mock_boto_client.assert_called_once_with(
            "ssm", config=custom_config, endpoint_url="http://localhost:4566"
        )

    @patch("boto3.client")
    def test_client_reuse(self, mock_boto_client):
        """Test that client is created once and reused."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        mock_client.get_parameter.return_value = {"Parameter": {"Value": "value"}}

        service = SsmService()

        # Make multiple calls
        service.get_parameter_value("flag1")
        service.get_parameter_value("flag2")

        # Client should be created only once
        assert mock_boto_client.call_count == 1
