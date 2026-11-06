"""flagd-testbed's ``config.feature``: option defaults, environment variables and precedence.

It builds a ``Config`` and reads it back, so it needs no backend.
"""

from __future__ import annotations

import re
import typing
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from openfeature.contrib.provider.flagd.config import CacheType, Config, ResolverType

UNSUPPORTED_TAGS = {"targetURI": "target URI", "unixsocket": "unix sockets"}
"""Example tags for options this provider does not have, with what they name."""

scenarios(
    str(Path(__file__).parents[1] / "openfeature/test-harness/gherkin/config.feature")
)


@pytest.fixture(autouse=True)
def _skip_unsupported(request: pytest.FixtureRequest) -> None:
    for marker in request.node.iter_markers():
        if marker.name in UNSUPPORTED_TAGS:
            pytest.skip(
                f"this provider does not support {UNSUPPORTED_TAGS[marker.name]}"
            )


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def _string_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


_CONVERTERS: dict[str, typing.Callable[[str], typing.Any]] = {
    "Integer": int,
    "Long": int,
    "String": str,
    "Boolean": lambda raw: raw.lower() in ("yes", "true", "t", "1"),
    "ResolverType": lambda raw: ResolverType(raw.lower()),
    "CacheType": CacheType,
    "StringList": _string_list,
}


@pytest.fixture
def option_values() -> dict[str, typing.Any]:
    return {}


@given(
    parsers.re(
        r'^an option "(?P<option>[^"]+)" of type "(?P<type_name>[^"]+)" '
        r'with value "(?P<value>[^"]*)"$'
    )
)
def an_option(
    option_values: dict[str, typing.Any], option: str, type_name: str, value: str
) -> None:
    option_values[_snake(option)] = _CONVERTERS[type_name](value)


@given(
    parsers.re(
        r'^an environment variable "(?P<env>[^"]+)" with value "(?P<value>[^"]*)"$'
    )
)
def an_environment_variable(
    monkeypatch: pytest.MonkeyPatch, env: str, value: str
) -> None:
    monkeypatch.setenv(env, value)


@when("a config was initialized", target_fixture="config_or_error")
def a_config_was_initialized(
    option_values: dict[str, typing.Any],
) -> tuple[Config | None, bool]:
    try:
        return Config(**option_values), False
    except AttributeError:
        return None, True


@when(
    parsers.re(r'^a config was initialized for "(?P<resolver>[^"]+)"$'),
    target_fixture="config_or_error",
)
def a_config_was_initialized_for(
    option_values: dict[str, typing.Any], resolver: str
) -> tuple[Config | None, bool]:
    try:
        return Config(resolver=ResolverType(resolver), **option_values), False
    except AttributeError:
        return None, True


@then(
    parsers.re(
        r'^the option "(?P<option>[^"]+)" of type "(?P<type_name>[^"]+)" '
        r'should have the value "(?P<value>[^"]*)"$'
    )
)
def the_option_should_have_the_value(
    config_or_error: tuple[Config | None, bool], option: str, type_name: str, value: str
) -> None:
    config, _ = config_or_error
    expected = None if value == "null" else _CONVERTERS[type_name](value)
    assert getattr(config, _snake(option)) == expected


@then("we should have an error")
def we_should_have_an_error(config_or_error: tuple[Config | None, bool]) -> None:
    _, error = config_or_error
    assert error
