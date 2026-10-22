"""The step that names a backend configuration, and the order it imposes.

One step rather than two is the whole point of it: the backend has to be serving
the named configuration *before* the provider connects. A scenario that said so
in a separate ``Given`` could put it after "a stable provider" and watch the
provider connect to the wrong flags, and the resulting failure would be reported
against the provider.

No canonical scenario names a configuration -- the baseline every control serves
is what they are written against -- so the step is driven directly.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from openfeature import api
from openfeature.contrib.tools.tck import (
    BackendControl,
    BackendType,
    Capability,
    ControllableInMemoryProvider,
    TckConfig,
    TckState,
    UnsupportedControlError,
    canonical_flag_set,
)
from openfeature.contrib.tools.tck.steps.provider_steps import (
    a_provider_with_configuration,
)
from openfeature.provider import FeatureProvider


class _RecordingControl:
    """A control that can serve a named configuration, and says when it was asked."""

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    @property
    def description(self) -> str:
        return "a control that records what it was asked"

    @property
    def backend_type(self) -> BackendType:
        return "custom"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...

    def serve_configuration(self, configuration: str) -> None:
        self.calls.append(f"serve:{configuration}")


class _OneConfigurationControl:
    """A control over a single in-process flag set, with no configuration to name."""

    @property
    def description(self) -> str:
        return "in-process control of an in-memory provider"

    @property
    def backend_type(self) -> BackendType:
        return "in-process"

    def prepare_scenario(self) -> None: ...

    def change_flag(self) -> None: ...


def _state(control: BackendControl, calls: list[str]) -> TckState:
    def new_provider() -> FeatureProvider:
        calls.append("create-provider")
        return ControllableInMemoryProvider(canonical_flag_set())

    config = TckConfig(
        name="configuration-step",
        control=control,
        new_provider=new_provider,
        capabilities={Capability.EVENTS},
    )
    return TckState(config=config)


@pytest.fixture(autouse=True)
def _release_providers() -> Iterator[None]:
    yield
    api.shutdown()
    api.clear_providers()


def test_the_configuration_is_served_before_the_provider_is_created() -> None:
    """The ordering the single step exists to guarantee."""
    calls: list[str] = []
    state = _state(_RecordingControl(calls), calls)

    a_provider_with_configuration(state, "stable", "metadata")

    assert calls == ["serve:metadata", "create-provider"]
    assert state.client is not None


def test_a_backend_with_one_configuration_reports_the_missing_operation() -> None:
    """Rather than quietly serving the baseline and asserting against its flags.

    A test-configuration bug: an extension scenario named a configuration, and
    only a control over a backend with more than one can answer that.
    """
    calls: list[str] = []
    state = _state(_OneConfigurationControl(), calls)

    with pytest.raises(UnsupportedControlError, match="serve_configuration"):
        a_provider_with_configuration(state, "stable", "metadata")

    assert calls == [], "the provider must not be created against the wrong flags"
