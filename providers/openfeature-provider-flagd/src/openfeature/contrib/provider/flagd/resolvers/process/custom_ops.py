# Re-export from openfeature-flagd-core for backward compatibility.
# The canonical implementation now lives in openfeature.contrib.tools.flagd.core.
from openfeature.contrib.tools.flagd.core.targeting.custom_ops import (  # noqa: F401
    Fraction,
    JsonLogicArg,
    JsonPrimitive,
    ends_with,
    fractional,
    parse_version,
    sem_ver,
    starts_with,
    string_comp,
)
