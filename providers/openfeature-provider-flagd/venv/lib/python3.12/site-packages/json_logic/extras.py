from typing import List, Any
from datetime import datetime, timezone

from .builtins import BUILTINS, to_number
from .types import Operations, JsonValue
from .cert_logic.builtins import parse_time

def op_time_since(data=None, timestamp=None, *_ignored) -> float:
    dt = parse_time(timestamp)
    return (datetime.utcnow().replace(tzinfo=timezone.utc) - dt).total_seconds() * 1000

def combinations(*lists: List[JsonValue]) -> List[List[JsonValue]]:
    combinations: List[List[JsonValue]] = []
    list_count = len(lists)
    if list_count > 0:
        stack = [0] * (list_count + 1)
        item: List[JsonValue] = [None] * list_count
        stack_ptr = 0

        while stack_ptr >= 0:
            if stack_ptr == list_count:
                combinations.append(item[:])
                stack_ptr -= 1
            else:
                list  = lists[stack_ptr]
                index = stack[stack_ptr]

                if index == len(list):
                    stack_ptr -= 1
                else:
                    item[stack_ptr]  = list[index]
                    stack[stack_ptr] = index + 1
                    stack_ptr += 1
                    stack[stack_ptr] = 0

    return combinations

EXTRAS_ONLY: Operations = {
    'now':        lambda *_ignored: datetime.utcnow().replace(tzinfo=timezone.utc),
    'hours':      lambda data=None, value=None, *_ignored: to_number(value) * 60 * 60 * 1000,
    'days':       lambda data=None, value=None, *_ignored: to_number(value) * 24 * 60 * 60 * 1000,
    'parseTime':  lambda data=None, value=None, *_ignored: parse_time(value),
    'formatTime': lambda data=None, value=None, *_ignored: parse_time(value).isoformat(),
    'timeSince':  op_time_since,
    'combinations': lambda data=None, *lists: combinations(*lists), # type: ignore
    'zip': lambda data=None, *lists: [list(item) for item in zip(*lists)],
}

EXTRAS: Operations = {
    **BUILTINS,
    **EXTRAS_ONLY,
}
