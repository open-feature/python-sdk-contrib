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

    from openfeature.contrib.tools.provider_tck import (
        Capability,
        InProcessControl,
        TckConfig,
        features_path,
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

    scenarios(features_path())

``scenarios()`` is pytest-bdd's own, called directly rather than wrapped: it
injects the generated tests into the *calling module* by walking the stack, so a
convenience wrapper around it would deposit them inside this package instead.

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

from .capability import ALL_CAPABILITIES, Capability
from .config import TckConfig
from .control import (
    BackendControl,
    ConnectionControl,
    UnsupportedControlError,
)
from .inprocess import InProcessControl
from .provider import (
    CHANGING_FLAG_KEY,
    ControllableInMemoryProvider,
    canonical_flag_set,
)

__all__ = [
    "ALL_CAPABILITIES",
    "CHANGING_FLAG_KEY",
    "BackendControl",
    "Capability",
    "ConnectionControl",
    "ControllableInMemoryProvider",
    "InProcessControl",
    "TckConfig",
    "UnsupportedControlError",
    "canonical_flag_set",
    "canonical_flags_json",
    "control_api_spec",
    "features_path",
]

# NOTE ON THE SOURCE OF TRUTH
#
# The files under features/ and flag_data/, and control-api.yaml, are NOT owned
# by this repository and are NOT committed to it. They are copies of the
# language-agnostic conformance artifacts defined in open-feature/spec under
# specification/assets/provider-tck/, which reaches this package as a git
# submodule at tools/openfeature-provider-tck/spec and is copied in at build
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

_PACKAGE = "openfeature.contrib.tools.provider_tck"


def features_path() -> str:
    """Return the directory holding the canonical feature files.

    Packaged with this distribution, so a consumer needs no submodule and no
    particular directory layout. Hand it to pytest-bdd's ``scenarios()``, which
    accepts an absolute path::

        scenarios(features_path())

    pytest-bdd generates one test per scenario -- and one per row of a Scenario
    Outline -- so failures name a scenario and ``-k`` selects one as usual.
    """
    return str(importlib.resources.files(_PACKAGE) / "features")


def canonical_flags_json() -> str:
    """Return the canonical flag set as raw JSON, in the flagd flag-definition format.

    This is the flag set every scenario assumes, and a backend under test must
    serve an equivalent one. The format is not what matters -- the keys, types,
    variant names and resolved values are. Seed them however your backend seeds
    flags.

    Exposed so an adopting provider can seed a backend from the canonical
    definition rather than transcribing it, transcription being the usual way
    the two drift apart.
    """
    ref = importlib.resources.files(_PACKAGE) / "flag_data" / "canonical-flags.json"
    return ref.read_text(encoding="utf-8")


def control_api_spec() -> str:
    """Return the OpenAPI document a containerised backend under test must implement."""
    ref = importlib.resources.files(_PACKAGE) / "control-api.yaml"
    return ref.read_text(encoding="utf-8")
