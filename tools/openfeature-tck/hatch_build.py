"""Hatch build hook to copy the canonical conformance assets into the package.

The feature files, the canonical flag set and the control-API document are owned
by open-feature/spec and reach this package through a git submodule, so nothing
in this repository can fork the definition of conformance. They are copied into
the source tree at build time and force-included into the distribution, which is
what lets an *adopter* install the wheel and run the suite with no submodule of
their own.
"""

import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Hatchling loads this file by path rather than importing it as part of a
# package, so its directory is not on sys.path and the sibling sync module --
# the single definition of what gets copied where -- would not be importable.
sys.path.insert(0, str(Path(__file__).parent))

from hatch_build_sync import FILES, PACKAGE_REL, SPEC_ASSETS, TREES, sync


class SpecAssetsCopyHook(BuildHookInterface):
    PLUGIN_NAME = "spec-assets-copy"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        copies = [root / PACKAGE_REL / dest for _, dest in TREES + FILES]

        # Building from a checkout: refresh from the submodule, so what ships is
        # always the revision the pin names. Building from an sdist: there is no
        # submodule, but the copies are already in the tree.
        if SPEC_ASSETS.exists():
            sync()
        elif not all(path.exists() for path in copies):
            missing = ", ".join(str(p) for p in copies if not p.exists())
            msg = (
                f"Conformance assets missing ({missing}) and the open-feature/spec "
                f"submodule is not checked out at {SPEC_ASSETS}. Run "
                "`git submodule update --init tools/openfeature-tck/spec`."
            )
            raise FileNotFoundError(msg)

        # Force-include the gitignored copies into both sdist and wheel.
        force = build_data.setdefault("force_include", {})
        for path in copies:
            for member in [path] if path.is_file() else path.rglob("*"):
                if member.is_file():
                    rel = str(member.relative_to(root))
                    force[rel] = rel
