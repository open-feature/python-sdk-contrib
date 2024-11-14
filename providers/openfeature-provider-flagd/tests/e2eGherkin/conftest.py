import typing

import pytest
from testcontainers.core.container import DockerContainer
from tests.e2eGherkin.flagd_container import FlagDContainer
from tests.e2eGherkin.steps import *  # noqa: F403

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType

JsonPrimitive = typing.Union[str, bool, float, int]


@pytest.fixture(autouse=True, scope="package")
def setup(request, port, image):
    container: DockerContainer = FlagDContainer(
        image=image,
        port=port,
    )
    # Setup code
    c = container.start()
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.GRPC,
            port=int(container.get_exposed_port(port)),
        )
    )

    def fin():
        c.stop()

    # Teardown code
    request.addfinalizer(fin)
