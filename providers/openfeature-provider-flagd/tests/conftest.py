import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider


@pytest.fixture()
def flagd_provider_client():
    api.set_provider(FlagdProvider())
    return api.get_client()
