import pytest
from unittest.mock import Mock, patch

from openfeature import api
from openfeature.contrib.provider.unleash import UnleashProvider


@pytest.fixture()
def unleash_provider_client():
    """Create Unleash provider with test client using mocked UnleashClient."""
    mock_client = Mock()
    mock_client.is_enabled.return_value = True

    with patch(
        "openfeature.contrib.provider.unleash.UnleashClient"
    ) as mock_unleash_client:
        mock_unleash_client.return_value = mock_client

        provider = UnleashProvider(
            url="http://localhost:4242", app_name="test-app", api_token="test-token"
        )
        api.set_provider(provider)
        yield api.get_client()
        provider.shutdown()
