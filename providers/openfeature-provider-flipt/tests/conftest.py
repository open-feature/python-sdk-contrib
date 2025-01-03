import pytest

from openfeature.contrib.provider.flipt import FliptProvider


@pytest.fixture
def flipt_provider():
    return FliptProvider("http://localhost:8080")
