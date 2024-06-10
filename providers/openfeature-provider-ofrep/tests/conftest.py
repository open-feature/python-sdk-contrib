import pytest

from openfeature.contrib.provider.ofrep import OFREPProvider


@pytest.fixture
def ofrep_provider():
    return OFREPProvider("http://localhost:8080")
