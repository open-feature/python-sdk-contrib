"""Hatch build hook to copy test-harness evaluator files into the package."""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

# Relative to the testkit package root
TEST_HARNESS_EVALUATOR = Path(
    "../../providers/openfeature-provider-flagd/openfeature/test-harness/evaluator"
)
DEST_BASE = "src/openfeature/contrib/tools/flagd/testkit"


class TestHarnessCopyHook(BuildHookInterface):
    PLUGIN_NAME = "test-harness-copy"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        src = root / TEST_HARNESS_EVALUATOR

        # When building wheel from sdist, the submodule isn't available
        # but the files were already force-included in the sdist.
        if not src.exists():
            return

        force = build_data.setdefault("force_include", {})

        # Map submodule gherkin files -> package features/
        gherkin_src = src / "gherkin"
        for path in gherkin_src.rglob("*"):
            if path.is_file():
                rel = path.relative_to(gherkin_src)
                force[str(path)] = f"{DEST_BASE}/features/{rel}"

        # Map submodule flag files -> package flag_data/
        flags_src = src / "flags"
        for path in flags_src.rglob("*"):
            if path.is_file():
                rel = path.relative_to(flags_src)
                force[str(path)] = f"{DEST_BASE}/flag_data/{rel}"
