import pytest
from open_feature import open_feature_api as api

from open_feature_contrib.providers.flagd import FlagdProvider


@pytest.fixture()
def flagd_provider_client():
    api.set_provider(FlagdProvider())
    return api.get_client()
