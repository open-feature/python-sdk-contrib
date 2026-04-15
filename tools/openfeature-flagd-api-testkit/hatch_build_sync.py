"""Copy test-harness evaluator files into the package source tree.

Used by `poe sync-test-harness` for local development and CI testing.
The hatch build hook (hatch_build.py) handles inclusion in wheel/sdist.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TEST_HARNESS_EVALUATOR = (
    ROOT / "../../providers/openfeature-provider-flagd/openfeature/test-harness/evaluator"
).resolve()
DEST_BASE = ROOT / "src/openfeature/contrib/tools/flagd/testkit"


def sync() -> None:
    if not TEST_HARNESS_EVALUATOR.exists():
        msg = (
            f"Test harness evaluator not found at {TEST_HARNESS_EVALUATOR}. "
            "Make sure submodules are initialized."
        )
        raise FileNotFoundError(msg)

    for src_name, dest_name in [("gherkin", "features"), ("flags", "flag_data")]:
        src = TEST_HARNESS_EVALUATOR / src_name
        dest = DEST_BASE / dest_name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)


if __name__ == "__main__":
    sync()
