from collections.abc import Awaitable, Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TypeVar, Union

import aiobotocore.endpoint
import boto3
import botocore.awsrequest
import botocore.retries.standard
import pytest
from botocore.config import Config
from moto import mock_aws

from openfeature.contrib.provider.awsssm import (
    AwsSsmProvider,
    AwsSsmProviderConfig,
    CacheConfig,
)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class _PatchedAWSResponseContent:
    """Patched version of `botocore.awsrequest.AWSResponse.content`."""

    content: Union[bytes, Awaitable[bytes]]

    def decode(self, encoding: str) -> str:
        assert isinstance(self.content, bytes)
        return self.content.decode(encoding)

    def __await__(self) -> Iterator[bytes]:
        async def _generate_async() -> bytes:
            if isinstance(self.content, Awaitable):
                return await self.content
            else:
                return self.content

        return _generate_async().__await__()


class PatchedAWSResponse:
    """Patched version of `botocore.awsrequest.AWSResponse`."""

    def __init__(self, response: botocore.awsrequest.AWSResponse) -> None:
        self._response = response
        self.status_code = response.status_code
        self.headers = response.headers
        self.url = response.url
        self.content = _PatchedAWSResponseContent(response.content)
        self.raw = response.raw
        if not hasattr(self.raw, "raw_headers"):
            self.raw.raw_headers = {}


class PatchedRetryContext(botocore.retries.standard.RetryContext):
    """Patched version of `botocore.retries.standard.RetryContext`."""

    def __init__(self, *args, **kwargs):
        if kwargs.get("http_response"):
            kwargs["http_response"] = PatchedAWSResponse(kwargs["http_response"])
        super().__init__(*args, **kwargs)


def _factory(
    original: Callable[[botocore.awsrequest.AWSResponse, T], Awaitable[R]],
) -> Callable[[botocore.awsrequest.AWSResponse, T], Awaitable[R]]:
    async def patched_convert_to_response_dict(
        http_response: botocore.awsrequest.AWSResponse, operation_model: T
    ) -> R:
        return await original(PatchedAWSResponse(http_response), operation_model)  # type: ignore[arg-type]

    return patched_convert_to_response_dict


@contextmanager
def mock_aio_aws(monkeypatch) -> Generator[None, None, None]:
    monkeypatch.setattr(
        aiobotocore.endpoint,
        "convert_to_response_dict",
        _factory(aiobotocore.endpoint.convert_to_response_dict),
    )
    monkeypatch.setattr(botocore.retries.standard, "RetryContext", PatchedRetryContext)

    with mock_aws():
        yield


@pytest.fixture
def mock_aws_patched(monkeypatch):
    with mock_aio_aws(monkeypatch):
        yield


@pytest.fixture
def ssm_client(mock_aws_patched):
    client = boto3.client("ssm", region_name="us-east-1")
    yield client


@pytest.fixture
def provider():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
    )
    return AwsSsmProvider(config=config)


@pytest.fixture
def cached_provider():
    config = AwsSsmProviderConfig(
        config=Config(region_name="us-east-1"),
        cache_config=CacheConfig(cache_type="lru", size=100),
    )
    return AwsSsmProvider(config=config)
