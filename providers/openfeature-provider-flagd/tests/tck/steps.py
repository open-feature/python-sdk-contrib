"""Step definitions for flagd-testbed's TCK extensions, beyond the TCK's own vocabulary.

Two kinds. The flagd glue: provider options, which a scenario records before the
TCK's ``a stable provider`` builds the provider, and the envoy listener. And three
generic steps the extensions use that this TCK does not define yet: a typed
context key, a nested context property, and the ``fatal`` client state.
"""

from __future__ import annotations

import re
import typing

from pytest_bdd import given, parsers, then

from openfeature.contrib.provider.flagd.config import CacheType
from openfeature.contrib.tools.tck import RunningBackend, TckState
from openfeature.contrib.tools.tck.values import parse_table_value
from openfeature.evaluation_context import EvaluationContext
from openfeature.provider import ProviderStatus
from tests.tck.suite import ENVOY_FORBIDDEN_PORT, ENVOY_SERVICE, TESTBED

_OPTION_NAMES = {"resolver": "resolver_type"}
"""Option names that do not follow from camelCase to snake_case."""


def _option_name(name: str) -> str:
    return _OPTION_NAMES.get(name) or re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _option_value(name: str, type_name: str, raw: str) -> typing.Any:
    if type_name == "CacheType":
        return CacheType(raw.lower())
    value = parse_table_value(type_name, raw)
    if name == "certPath":
        return str(TESTBED / value)
    return value


@given(
    parsers.re(
        r'^an option "(?P<name>[^"]*)" of type "(?P<type_name>[^"]*)" '
        r'with value "(?P<raw>[^"]*)"$'
    )
)
def an_option(
    provider_options: dict[str, typing.Any], name: str, type_name: str, raw: str
) -> None:
    provider_options[_option_name(name)] = _option_value(name, type_name, raw)


@given("the provider connects to envoy's forbidden listener")
def the_provider_connects_to_the_forbidden_listener(
    provider_options: dict[str, typing.Any], tck_backend: RunningBackend
) -> None:
    endpoint = tck_backend.endpoint
    provider_options["host"] = endpoint.host_of(ENVOY_SERVICE)
    provider_options["port"] = endpoint.port(
        ENVOY_FORBIDDEN_PORT, service=ENVOY_SERVICE
    )


def _cell(value: str) -> str:
    r"""An Examples cell as written: pytest-bdd 8 doubles every backslash in one.

    The fractional outline hashes ``A\u0000B`` as those eight characters, as
    Cucumber and godog pass it. The steps below take their values from cells
    only; a backslash written in the step text itself would be halved too.
    """
    return value.replace("\\\\", "\\")


def _add_attribute(tck_state: TckState, key: str, value: typing.Any) -> None:
    context = tck_state.evaluation_context or EvaluationContext()
    tck_state.evaluation_context = EvaluationContext(
        targeting_key=context.targeting_key,
        attributes={**context.attributes, key: value},
    )


@given(
    parsers.re(
        r'^a context containing a key "(?P<key>[^"]*)", with type "(?P<type_name>[^"]*)" '
        r'and with value "(?P<raw>[^"]*)"$'
    )
)
def a_context_containing_a_key(
    tck_state: TckState, key: str, type_name: str, raw: str
) -> None:
    # An attribute even when the key is "targetingKey": the fractional scenarios
    # pass a non-string there and expect it not to count as the targeting key.
    _add_attribute(tck_state, key, parse_table_value(type_name, _cell(raw)))


@given(
    parsers.re(
        r'^a context containing a nested property with outer key "(?P<outer>[^"]*)" '
        r'and inner key "(?P<inner>[^"]*)", with value "(?P<value>[^"]*)"$'
    )
)
def a_context_containing_a_nested_property(
    tck_state: TckState, outer: str, inner: str, value: str
) -> None:
    _add_attribute(tck_state, outer, {inner: _cell(value)})


@then("the client should be in fatal state")
def the_client_should_be_in_fatal_state(tck_state: TckState) -> None:
    status = tck_state.require_client().get_provider_status()
    assert status == ProviderStatus.FATAL, f"expected FATAL, got {status}"
