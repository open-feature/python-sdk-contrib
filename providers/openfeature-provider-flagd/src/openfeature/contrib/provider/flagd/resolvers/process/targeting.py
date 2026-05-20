# Re-export from openfeature-flagd-core for backward compatibility.
# The canonical implementation now lives in openfeature.contrib.tools.flagd.core.
from openfeature.contrib.tools.flagd.core.targeting.targeting import (  # noqa: F401
    OPERATORS,
    targeting,
)
