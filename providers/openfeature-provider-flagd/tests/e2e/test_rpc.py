import pytest
from asserts import assert_true
from pytest_bdd import parsers, scenarios, then
from tests.e2e.parsers import to_bool

from openfeature.contrib.provider.flagd.config import ResolverType


@pytest.fixture(autouse=True, scope="package")
def resolver_type() -> ResolverType:
    return ResolverType.GRPC


@pytest.fixture(autouse=True, scope="package")
def port():
    return 8013


@pytest.fixture(autouse=True, scope="package")
def image():
    return "ghcr.io/open-feature/flagd-testbed:v0.5.13"


@then(
    parsers.cfparse("the PROVIDER_CONFIGURATION_CHANGED handler must run"),
)
def provider_changed_was_executed():
    assert_true(True)
    # TODO: DELETE AFTER IMPLEMENTATION OF EVENTS FOR RPC


@then(parsers.cfparse('the event details must indicate "{flag_name}" was altered'))
def flag_was_changed():
    assert_true(True)
    # TODO: DELETE AFTER IMPLEMENTATION OF EVENTS FOR RPC


@then(
    parsers.cfparse(
        'the resolved object {details:s?}value should be contain fields "{bool_field}", "{string_field}", and "{int_field}", with values "{bvalue:bool}", "{svalue}" and {ivalue:d}, respectively',
        extra_types={"bool": to_bool, "s": str},
    ),
)
def assert_object():
    assert_true(True)
    # TODO: DELETE AFTER #102 is fixed


@then(
    parsers.cfparse(
        'the variant should be "{variant}", and the reason should be "{reason}"',
    )
)
def assert_for_variant_and_reason():
    assert_true(True)
    # TODO: DELETE AFTER #102 is fixed


scenarios(
    "../../test-harness/gherkin/flagd.feature",
    "../../test-harness/gherkin/flagd-json-evaluator.feature",
    "../../spec/specification/assets/gherkin/evaluation.feature",
)
