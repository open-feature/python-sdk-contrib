"""Copy the flagd JSON schemas from the schemas submodule into the package.

Used by `poe sync-schemas` after the submodule has been updated. The copies
are committed, because uv_build does not support build hooks yet.
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SCHEMAS_SUBMODULE = (
    ROOT / "../../providers/openfeature-provider-flagd/openfeature/schemas/json"
).resolve()
DEST = ROOT / "src/openfeature/contrib/tools/flagd/core/schemas"
SCHEMA_FILES = ("flags.json", "targeting.json")


def sync() -> None:
    if not SCHEMAS_SUBMODULE.exists():
        msg = (
            f"flagd schemas not found at {SCHEMAS_SUBMODULE}. "
            "Make sure submodules are initialized."
        )
        raise FileNotFoundError(msg)

    DEST.mkdir(parents=True, exist_ok=True)
    for name in SCHEMA_FILES:
        shutil.copyfile(SCHEMAS_SUBMODULE / name, DEST / name)


if __name__ == "__main__":
    sync()
