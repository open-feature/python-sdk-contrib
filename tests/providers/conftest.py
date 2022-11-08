import pytest
from open_feature import open_feature_api as api

from open_feature_contrib.providers.flagd import FlagDProvider


@pytest.fixture()
def flagd_provider_client():
    api.set_provider(FlagDProvider())
    return api.get_client()
