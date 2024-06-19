from __future__ import annotations

from typing import Union, List, Dict, Callable
from datetime import date, datetime

__all__ = 'JsonValue',

# pylance seems to be ulessly broken even for these simple types
JsonValue = Union[int, float, bool, str, date, datetime, None, List['JsonValue'], Dict[str, 'JsonValue']] # type: ignore

Operation = Callable[..., JsonValue] # type: ignore
Operations = Dict[str, Union[Operation, 'Operations']] # type: ignore
