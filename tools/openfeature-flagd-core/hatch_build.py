"""Hatch build hook to copy the flagd JSON schemas into the package."""

import shutil
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

DEST = Path("src/openfeature/contrib/tools/flagd/core/schemas")
SCHEMA_FILES = ("flags.json", "targeting.json")


class SchemaCopyHook(BuildHookInterface):
    PLUGIN_NAME = "schema-copy"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        dest = root / DEST
        src = (
            root / "../../providers/openfeature-provider-flagd/openfeature/schemas/json"
        )

        # Copy from submodule if files don't exist yet
        if src.exists():
            dest.mkdir(parents=True, exist_ok=True)
            for name in SCHEMA_FILES:
                if not (dest / name).exists():
                    shutil.copyfile(src / name, dest / name)

        # Force-include gitignored files into both sdist and wheel
        force = build_data.setdefault("force_include", {})
        for name in SCHEMA_FILES:
            if (dest / name).exists():
                rel = str(DEST / name)
                force[rel] = rel
