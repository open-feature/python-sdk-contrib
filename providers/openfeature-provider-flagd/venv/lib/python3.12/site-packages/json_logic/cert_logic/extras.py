from ..extras import EXTRAS as JSONLOGIC_EXTRAS
from ..types import Operations
from .builtins import BUILTINS, to_bool

EXTRAS: Operations = {
    **JSONLOGIC_EXTRAS,
    '!!': lambda data=None, value=None, *_ignored: to_bool(value),
    **BUILTINS,
}
