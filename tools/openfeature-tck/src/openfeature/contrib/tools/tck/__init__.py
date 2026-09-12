"""The OpenFeature Provider Conformance Suite (TCK) for Python.

The suite answers one question: does this provider map its backend onto the
OpenFeature provider contract correctly? It is the Python implementation of
`Appendix F`_ of the specification, and it runs the same Gherkin scenarios,
against the same canonical flag set, that every other language's TCK runs. That
shared basis is the whole point -- "conformant" only means something if the
question is identical everywhere.

**What a provider author writes.** One fixture and one call::

    import pytest
    from pytest_bdd import scenarios

    from openfeature.contrib.tools.tck import (
        Capability,
        InProcessControl,
        TckConfig,
        feature_paths,
    )

    @pytest.fixture(scope="session")
    def tck_config():
        control = InProcessControl()
        return TckConfig(
            name="my-provider",
            control=control,
            new_provider=control.new_provider,
            capabilities={Capability.EVENTS, Capability.OBJECT},
        )

    scenarios(*feature_paths())

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

from .capability import DECLARABLE_CAPABILITIES, RESERVED_CAPABILITIES, Capability
from .config import KnownDeviation, TckConfig
from .control import (
    BackendControl,
    ConnectionControl,
    UnsupportedControlError,
)
from .extensions import (
    EXTENSIONS_DIRECTORY,
    feature_paths,
    features_path,
)
from .httpcontrol import (
    DEFAULT_CONFIGURATION,
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
from .state import TckState

__all__ = [
    "CHANGING_FLAG_KEY",
    "DECLARABLE_CAPABILITIES",
    "DEFAULT_CONFIGURATION",
    "EXTENSIONS_DIRECTORY",
    "RESERVED_CAPABILITIES",
    "BackendControl",
    "Capability",
    "ConnectionControl",
    "ControlApiError",
    "ControllableInMemoryProvider",
    "HttpControl",
    "InProcessControl",
    "KnownDeviation",
    "TckConfig",
    "TckState",
    "UnsupportedControlError",
    "canonical_flag_set",
    "canonical_flags_json",
    "control_api_spec",
    "feature_paths",
    "features_path",
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
