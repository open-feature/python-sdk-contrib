import typing

import pytest
from testcontainers.core.container import DockerContainer
from tests.e2e.flagd_container import FlagdContainer
from tests.e2e.steps import *  # noqa: F403

JsonPrimitive = typing.Union[str, bool, float, int]

TEST_HARNESS_PATH = "../../openfeature/test-harness"
SPEC_PATH = "../../openfeature/spec"


# running all gherkin tests, except the ones, not implemented
def pytest_collection_modifyitems(config):
    marker = "not customCert and not unixsocket and not sync"

    # this seems to not work with python 3.8
    if hasattr(config.option, "markexpr") and config.option.markexpr == "":
        config.option.markexpr = marker


@pytest.fixture(autouse=True, scope="module")
def setup(request, port, image):
    container: DockerContainer = FlagdContainer(
        image=image,
        port=port,
    )
    # Setup code
    c = container.start()

    def fin():
        c.stop()

    # Teardown code
    request.addfinalizer(fin)

    return c.get_exposed_port(port)
