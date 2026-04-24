import pytest

from openfeature.contrib.provider.flagd.config import ResolverType
from tests.e2e.testfilter import TestFilter

resolver = ResolverType.RPC
feature_list = [
    "~targetURI",
    "~unixsocket",
    "~sync",
    "~metadata",
    "~deprecated",
    "~fractional-v1",
    "~operator-errors",
    "~semver-v-prefix",
    "~fractional-single-entry",
    "~semver-numeric-context",
]
# TODO remove last 4 tags when adjusted flagd is released


def pytest_collection_modifyitems(config, items):
    test_filter = TestFilter(
        config, feature_list=feature_list, resolver=resolver.value, base_path=__file__
    )
    test_filter.filter_items(items)


@pytest.fixture()
def resolver_type() -> ResolverType:
    return resolver
