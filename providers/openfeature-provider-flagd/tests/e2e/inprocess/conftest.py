import pytest

from openfeature.contrib.provider.flagd.config import ResolverType
from tests.e2e.testfilter import TestFilter

resolver = ResolverType.IN_PROCESS
feature_list = ["~targetURI", "~unixsocket"]


def pytest_collection_modifyitems(config, items):
    test_filter = TestFilter(
        config, feature_list=feature_list, resolver=resolver.value, base_path=__file__
    )
    test_filter.filter_items(items)


@pytest.fixture()
def resolver_type() -> ResolverType:
    return resolver
