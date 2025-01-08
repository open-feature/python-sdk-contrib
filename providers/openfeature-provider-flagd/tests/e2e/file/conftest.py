import tempfile
import threading

import pytest

from openfeature.contrib.provider.flagd.config import ResolverType
from tests.e2e.step.provider_steps import changefile, write_test_file
from tests.e2e.testfilter import TestFilter

# from tests.e2e.step.config_steps import *
# from tests.e2e.step.event_steps import *
# from tests.e2e.step.provider_steps import *

resolver = ResolverType.FILE
feature_list = {
    "~targetURI",
    "~customCert",
    "~unixsocket",
    "~events",
    "~sync",
    "~caching",
    "~grace",
}


def pytest_collection_modifyitems(config, items):
    test_filter = TestFilter(
        config, feature_list=feature_list, resolver=resolver.value, base_path=__file__
    )
    test_filter.filter_items(items)


@pytest.fixture()
def resolver_type() -> ResolverType:
    return resolver


@pytest.fixture(params=["json", "yaml"], scope="module", autouse=True)
def file_name(request, all_flags):
    extension = request.param
    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix="." + extension
    ) as outfile:
        write_test_file(outfile, all_flags)

        update_thread = threading.Thread(
            target=changefile, args=("changing-flag", all_flags, outfile)
        )
        update_thread.daemon = True  # Makes the thread exit when the main program exits
        update_thread.start()
        yield outfile
        return outfile
