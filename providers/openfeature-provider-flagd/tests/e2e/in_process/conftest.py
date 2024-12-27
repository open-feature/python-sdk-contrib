import pytest

from openfeature.contrib.provider.flagd.config import ResolverType
from tests.e2e.testFilter import TestFilter

# from tests.e2e.step.config_steps import *
# from tests.e2e.step.event_steps import *
# from tests.e2e.step.provider_steps import *

resolver = ResolverType.IN_PROCESS
feature_list = {
    "~targetURI",
    "~customCert",
    "~unixsocket",
    "~events",
    "~sync",
    "~caching",
    "~reconnect",
    "~grace",
    "~connect",
    "~targeting",
}


def pytest_collection_modifyitems(config, items):
    test_filter = TestFilter(
        config, feature_list=feature_list, resolver=resolver.value, base_path=__file__
    )
    test_filter.filter_items(items)


@pytest.fixture()
def resolver_type() -> ResolverType:
    return resolver
