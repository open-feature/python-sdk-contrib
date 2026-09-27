"""Hatch build hook to ship the generated protobuf modules in the distribution.

Generating them is the job of hatch_build_protoc.py, which `poe generate-protos`
also runs; this hook only makes sure a build of a checkout is generated from the
submodule pin and that the gitignored results end up inside the wheel and sdist.
"""

import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Hatchling loads this file by path rather than importing it as part of a
# package, so its directory is not on sys.path and the sibling generation module
# -- the single definition of how protoc is invoked -- would not be importable.
sys.path.insert(0, str(Path(__file__).parent))

from hatch_build_protoc import generate


class ProtobufGenerateHook(BuildHookInterface):
    PLUGIN_NAME = "protobuf-generate"

    def initialize(self, version: str, build_data: dict) -> None:
        # Building from a checkout: regenerate, so what ships always matches the
        # revision the submodule pin names. Building a wheel from an sdist: there
        # is no submodule, `generate` finds nothing, and the modules are already
        # in the tree because the sdist carries them.
        outputs = generate()
        build_data["artifacts"] += [path.as_posix() for path in outputs]
