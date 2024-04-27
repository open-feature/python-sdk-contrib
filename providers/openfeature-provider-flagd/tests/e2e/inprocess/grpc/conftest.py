import pytest
from pytest_bdd import given

from openfeature import api
from openfeature.client import OpenFeatureClient
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType


@pytest.fixture
def port():
    # Port for flagd-sync, override to 9091 to test unstable version
    return 9090


@given("a flagd provider is set", target_fixture="client")
def setup_provider(port: int) -> OpenFeatureClient:
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            port=port,
        )
    )
    return api.get_client()
