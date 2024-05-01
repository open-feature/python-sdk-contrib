from pytest_bdd import given

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType


@given("a flagd provider is set", target_fixture="client")
def setup_provider(flag_file):
    provider = FlagdProvider(
        resolver_type=ResolverType.IN_PROCESS,
        offline_flag_source_path=flag_file,
        offline_poll_interval_seconds=0.1,
    )
    api.set_provider(provider)
    yield api.get_client()
    provider.shutdown()
