from typing import TYPE_CHECKING, Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from openfeature.exception import FlagNotFoundError, GeneralError

if TYPE_CHECKING:
    import aioboto3
    from mypy_boto3_ssm.client import SSMClient
else:
    try:
        import aioboto3
    except ImportError:
        aioboto3 = None


class SsmService:
    """
    Service for interacting with AWS SSM Parameter Store.

    Supports both synchronous (boto3) and asynchronous (aioboto3) operations.
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        endpoint_url: Optional[str] = None,
        enable_decryption: bool = False,
    ) -> None:
        """
        Initialize the SSM service.

        Args:
            config: boto3 Config object (includes region_name, retries, etc.)
            endpoint_url: Custom endpoint URL for SSM
            enable_decryption: Whether to decrypt SecureString parameters
        """
        self.enable_decryption = enable_decryption
        self._client: Optional[SSMClient] = None
        self._async_session: Optional[aioboto3.Session] = None
        self._client_kwargs: dict[str, Any] = {}
        if endpoint_url:
            self._client_kwargs["endpoint_url"] = endpoint_url
        if config:
            self._client_kwargs["config"] = config

    def _get_client(self) -> "SSMClient":
        """Get or create boto3 SSM client."""
        if self._client is None:
            self._client = boto3.client("ssm", **self._client_kwargs)
        return self._client

    def _normalize_parameter_name(self, flag_key: str) -> str:
        """
        Normalize flag key to SSM parameter name.

        Args:
            flag_key: The flag key

        Returns:
            SSM parameter name (with leading slash)
        """
        if not flag_key.startswith("/"):
            return f"/{flag_key}"
        return flag_key

    def _handle_client_error(self, error: ClientError, parameter_name: str) -> None:
        """
        Handle ClientError exceptions from AWS.

        Args:
            error: The ClientError exception
            parameter_name: The parameter name that caused the error

        Raises:
            FlagNotFoundError: If the parameter does not exist
            GeneralError: For other AWS errors
        """
        error_code = error.response.get("Error", {}).get("Code", "")
        if error_code == "ParameterNotFound":
            raise FlagNotFoundError(
                f"Parameter '{parameter_name}' not found"
            ) from error
        if error_code in ("AccessDeniedException", "AccessDenied"):
            raise GeneralError(
                f"Access denied to parameter '{parameter_name}'"
            ) from error
        if error_code in ("ThrottlingException", "TooManyRequestsException"):
            raise GeneralError(
                f"Throttled while accessing parameter '{parameter_name}'"
            ) from error
        raise GeneralError(f"AWS SSM error: {error}") from error

    def get_parameter_value(self, flag_key: str) -> str:
        """
        Get parameter value from SSM.

        Args:
            flag_key: The flag key

        Returns:
            The parameter value as a string

        Raises:
            FlagNotFoundError: If the parameter does not exist
            GeneralError: For other AWS errors
        """
        parameter_name = self._normalize_parameter_name(flag_key)
        client = self._get_client()

        try:
            response = client.get_parameter(
                Name=parameter_name, WithDecryption=self.enable_decryption
            )
            parameter = response.get("Parameter", {})
            value = parameter.get("Value")
            if value is None:
                raise GeneralError(
                    f"Parameter {parameter_name} exists but has no value"
                )
            return str(value)
        except ClientError as e:
            self._handle_client_error(e, parameter_name)
            raise

    async def get_parameter_value_async(self, flag_key: str) -> str:
        """
        Get parameter value from SSM asynchronously.

        Args:
            flag_key: The flag key

        Returns:
            The parameter value as a string

        Raises:
            FlagNotFoundError: If the parameter does not exist
            GeneralError: For other AWS errors
            ImportError: If aioboto3 is not installed
        """
        if aioboto3 is None:
            raise ImportError(
                "aioboto3 is required for async support. "
                "Install with: pip install openfeature-provider-aws-ssm[async]"
            )

        parameter_name = self._normalize_parameter_name(flag_key)

        if self._async_session is None:
            self._async_session = aioboto3.Session()

        async with self._async_session.client("ssm", **self._client_kwargs) as client:
            try:
                response = await client.get_parameter(
                    Name=parameter_name, WithDecryption=self.enable_decryption
                )
                parameter = response.get("Parameter", {})
                value = parameter.get("Value")
                if value is None:
                    raise GeneralError(
                        f"Parameter {parameter_name} exists but has no value"
                    )
                return str(value)
            except ClientError as e:
                self._handle_client_error(e, parameter_name)
                raise
