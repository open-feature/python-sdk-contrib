import time

import pytest

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider
from openfeature.contrib.provider.flagd.config import ResolverType
from openfeature.evaluation_context import EvaluationContext
from openfeature.event import ProviderEvent
from openfeature.exception import ErrorCode
from openfeature.flag_evaluation import Reason


def create_client(provider: FlagdProvider):
    api.set_provider(provider)
    return api.get_client()


@pytest.mark.parametrize(
    "file_name",
    [
        "not-a-flag.json",
        "basic-flag-wrong-structure.json",
        "basic-flag-invalid.not-json",
        "basic-flag-wrong-variant.json",
        "basic-flag-broken-state.json",
        "basic-flag-broken-variants.json",
        "basic-flag-broken-default.json",
        "basic-flag-broken-targeting.json",
    ],
)
def test_file_load_errors(file_name: str):
    client = create_client(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=f"tests/flags/{file_name}",
        )
    )

    res = client.get_boolean_details("basic-flag", False)

    assert res.value is False
    assert res.reason == Reason.ERROR
    assert res.error_code == ErrorCode.FLAG_NOT_FOUND


@pytest.mark.parametrize(
    "file_name",
    [
        "invalid-semver-op.json",
        "invalid-semver-args.json",
        "invalid-stringcomp-args.json",
        "invalid-fractional-args.json",
        "invalid-fractional-weights.json",
    ],
)
def test_json_logic_parse_errors(file_name: str):
    client = create_client(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path=f"tests/flags/{file_name}",
        )
    )

    res = client.get_string_details("basic-flag", "fallback", EvaluationContext("123"))

    assert res.value == "default"
    assert res.reason == Reason.DEFAULT


def test_flag_disabled():
    client = create_client(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            offline_flag_source_path="tests/flags/basic-flag-disabled.json",
        )
    )

    res = client.get_string_details("basic-flag", "fallback", EvaluationContext("123"))

    assert res.value == "fallback"
    assert res.reason == Reason.DISABLED


@pytest.mark.parametrize("wait", (0.5, 0.25))
def test_grpc_sync_fail_deadline(wait: float):
    init_failed = False

    def fail(*args, **kwargs):
        nonlocal init_failed
        init_failed = True

    api.get_client().add_handler(ProviderEvent.PROVIDER_ERROR, fail)

    t = time.time()
    api.set_provider(
        FlagdProvider(
            resolver_type=ResolverType.IN_PROCESS,
            port=99999,  # dead port to test failure
            timeout=wait,
        )
    )

    elapsed = time.time() - t
    assert abs(elapsed - wait) < 0.1
    assert init_failed
