"""Hatch build hook to copy test-harness evaluator files into the package."""

import shutil
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

DEST_BASE = Path("src/openfeature/contrib/tools/flagd/testkit")


class TestHarnessCopyHook(BuildHookInterface):
    PLUGIN_NAME = "test-harness-copy"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        features_dest = root / DEST_BASE / "features"
        flags_dest = root / DEST_BASE / "flag_data"

        # Copy from submodule if files don't exist yet
        if not features_dest.exists() or not flags_dest.exists():
            src = (
                root
                / "../../providers/openfeature-provider-flagd"
                / "openfeature/test-harness/evaluator"
            )
            if src.exists():
                if not features_dest.exists():
                    shutil.copytree(src / "gherkin", features_dest)
                if not flags_dest.exists():
                    shutil.copytree(src / "flags", flags_dest)

        # Force-include gitignored files into both sdist and wheel
        if features_dest.exists() and flags_dest.exists():
            force = build_data.setdefault("force_include", {})
            for dest_dir in (features_dest, flags_dest):
                for path in dest_dir.rglob("*"):
                    if path.is_file():
                        rel = str(path.relative_to(root))
                        force[rel] = rel
