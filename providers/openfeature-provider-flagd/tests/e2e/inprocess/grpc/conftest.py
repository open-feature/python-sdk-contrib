import pytest
from pytest_bdd import given, parsers, then, when
from tests.e2e.conftest import add_event_handler, assert_handlers

from openfeature import api
from openfeature.client import OpenFeatureClient, ProviderEvent
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
            timeout=0.1,
            retry_backoff_seconds=0.1,
        )
    )
    return api.get_client()


@when(parsers.cfparse('a flag with key "{key}" is modified'))
def modify_flag(key):
    # sync service will flip flag contents regularly
    pass


@given("flagd is unavailable", target_fixture="client")
def flagd_unavailable():
    return setup_provider(99999)


@when("a flagd provider is set and initialization is awaited")
def flagd_init(client: OpenFeatureClient, handles):
    add_event_handler(client, ProviderEvent.PROVIDER_ERROR, handles)
    add_event_handler(client, ProviderEvent.PROVIDER_READY, handles)


@then("an error should be indicated within the configured deadline")
def flagd_error(handles):
    assert_handlers(handles, ProviderEvent.PROVIDER_ERROR)
