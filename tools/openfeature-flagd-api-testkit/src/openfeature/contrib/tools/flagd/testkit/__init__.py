import importlib.resources
import typing


def get_features_path() -> str:
    """Return the path to the bundled feature files directory."""
    ref = importlib.resources.files("openfeature.contrib.tools.flagd.testkit") / "features"
    return str(ref)


def load_testkit_flags() -> str:
    """Load the bundled testkit-flags.json as a string."""
    ref = importlib.resources.files("openfeature.contrib.tools.flagd.testkit") / "flag_data" / "testkit-flags.json"
    return ref.read_text(encoding="utf-8")
