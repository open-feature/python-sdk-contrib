"""The OpenFeature Provider Conformance Suite (TCK) for Python.

The suite answers one question: does this provider map its backend onto the
OpenFeature provider contract correctly? It is the Python implementation of
`Appendix F`_ of the specification, and it runs the same Gherkin scenarios,
against the same canonical flag set, that every other language's TCK runs. That
shared basis is the whole point -- "conformant" only means something if the
question is identical everywhere.

**What a provider author writes.** Two fixtures and one call::

    import pytest
    from pytest_bdd import scenarios

    from openfeature.contrib.tools.tck import (
        Capability,
        ComposeBackend,
        RunningBackend,
        TckConfig,
        feature_paths,
    )

    @pytest.fixture(scope="session")
    def compose_backend():
        return ComposeBackend(
            compose_file="tests/tck/docker-compose.yaml",
            backend_ports=[8013],
        )

    @pytest.fixture(scope="session")
    def tck_config(tck_backend: RunningBackend):
        return TckConfig(
            name="my-provider",
            control=tck_backend.control,
            new_provider=lambda: MyProvider(
                host=tck_backend.endpoint.host,
                port=tck_backend.endpoint.port(8013),
            ),
            capabilities={Capability.EVENTS, Capability.OBJECT},
        )

    scenarios(*feature_paths())

The suite owns the container stack: it starts the Compose file once, discovers
the dynamically mapped host ports, builds the HTTP control against the control
API, waits until it accepts commands, and tears down after the last scenario.
See :mod:`~.compose`.

**A provider with no backend supplies its own control instead** -- in-memory,
environment-variable, file-based -- and needs no Compose file and no container
tooling::

    @pytest.fixture(scope="session")
    def tck_config():
        control = InProcessControl()
        return TckConfig(
            name="my-provider",
            control=control,
            new_provider=control.new_provider,
            capabilities={Capability.EVENTS, Capability.OBJECT},
        )

``scenarios()`` is pytest-bdd's own, called directly rather than wrapped: it
injects the generated tests into the *calling module* by walking the stack, so a
convenience wrapper around it would deposit them inside this package instead.
:func:`~.extensions.feature_paths` is the canonical assets plus a
``extensions`` directory beside the calling module, if there is one -- see
:mod:`~.extensions`.

The step definitions arrive through this package's pytest plugin, so there is
nothing to import for them and no ``conftest.py`` to write. Everything else --
registering the provider, awaiting events, resetting the backend between
scenarios, tearing down -- belongs to the TCK. If you find yourself writing test
infrastructure, that is a defect here rather than something for you to work
around.

.. _Appendix F: https://github.com/open-feature/spec/blob/main/specification/appendix-f-provider-conformance.md
"""

from __future__ import annotations

import importlib.resources

from .capability import (
    DECLARABLE_CAPABILITIES,
    INEXPRESSIBLE_CAPABILITIES,
    RESERVED_CAPABILITIES,
    Capability,
)
from .compose import (
    DEFAULT_BACKEND_SERVICE,
    DEFAULT_CONTROL_PORT,
    BackendEndpoint,
    ComposeBackend,
    RunningBackend,
    run_compose_backend,
)
from .config import KnownDeviation, TckConfig
from .control import (
    BackendControl,
    ConnectionControl,
    ControlApi,
    UnsupportedControlError,
)
from .extensions import (
    EXTENSIONS_DIRECTORY,
    canonical_root,
    feature_paths,
)
from .httpcontrol import (
    DEFAULT_CONFIGURATION,
    DEFAULT_STARTUP_TIMEOUT,
    ControlApiError,
    HttpControl,
)
from .inprocess import InProcessControl
from .provider import (
    CHANGING_FLAG_KEY,
    ControllableInMemoryProvider,
    canonical_flag_set,
    canonical_flags_json,
)
from .report import REPORT_DIR_ENV, SCHEMA_VERSION, Outcome
from .state import TckState

__all__ = [
    "CHANGING_FLAG_KEY",
    "DECLARABLE_CAPABILITIES",
    "DEFAULT_BACKEND_SERVICE",
    "DEFAULT_CONFIGURATION",
    "DEFAULT_CONTROL_PORT",
    "DEFAULT_STARTUP_TIMEOUT",
    "EXTENSIONS_DIRECTORY",
    "INEXPRESSIBLE_CAPABILITIES",
    "REPORT_DIR_ENV",
    "RESERVED_CAPABILITIES",
    "SCHEMA_VERSION",
    "BackendControl",
    "BackendEndpoint",
    "Capability",
    "ComposeBackend",
    "ConnectionControl",
    "ControlApi",
    "ControlApiError",
    "ControllableInMemoryProvider",
    "HttpControl",
    "InProcessControl",
    "KnownDeviation",
    "Outcome",
    "RunningBackend",
    "TckConfig",
    "TckState",
    "UnsupportedControlError",
    "canonical_flag_set",
    "canonical_flags_json",
    "canonical_root",
    "control_api_spec",
    "feature_paths",
    "run_compose_backend",
]

# NOTE ON THE SOURCE OF TRUTH
#
# The files under gherkin/ and flag_data/, and control-api.yaml, are NOT owned
# by this repository and are NOT committed to it. They are copies of the
# language-agnostic conformance artifacts defined in open-feature/spec under
# specification/assets/provider-tck/, which reaches this package as a git
# submodule at tools/openfeature-tck/spec and is copied in at build
# time by hatch_build.py. The copies are gitignored, so the only record of which
# spec revision this package targets is the submodule pin, and the two cannot
# drift apart unnoticed.
#
# They are copied into the distribution, so an adopter installing this package
# needs no submodule of their own; only a contributor to this package does.
#
# Changes belong in open-feature/spec first, followed by a bump of the submodule
# pin -- editing the copies locally forks the definition of conformance, which is
# the one thing this suite exists to prevent.
# See https://github.com/open-feature/spec/issues/417.

_PACKAGE = "openfeature.contrib.tools.tck"


def control_api_spec() -> str:
    """Return the OpenAPI document a containerised backend under test must implement."""
    ref = importlib.resources.files(_PACKAGE) / "control-api.yaml"
    return ref.read_text(encoding="utf-8")
