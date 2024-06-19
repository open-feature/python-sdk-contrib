from __future__ import annotations

from typing import Any, Optional
from datetime import datetime, date, time, timedelta, timezone, tzinfo
from math import isnan

import re

from ..types import Operations
from ..builtins import to_number, to_string, op_var, op_in, op_less_than, op_less_than_or_equal, op_greater_than, op_greater_than_or_equal

DATE_PATTERN = re.compile(r'^(\d{4})-(\d{2})-(\d{2})$')
DATE_TIME_PATTERN = re.compile(r'^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2}(\.\d+?)?)(?:Z|(?:(?P<tzsign>[+-])(?P<tzhour>\d{1,2}):?(?P<tzminute>\d{2})?))?$')

def to_bool(value: Any=None) -> bool:
    if value is None:
        return False

    if type(value) is bool:
        return value # type: ignore

    if isinstance(value, float):
        if isnan(value):
            return False
        return bool(value)

    if isinstance(value, (str, int, list, dict, bool)):
        return bool(value)

    # dict, date, datetime
    return True

def not_(value: Any=None) -> bool:
    if value is None:
        return True

    if type(value) is bool:
        return not value

    if isinstance(value, float):
        if isnan(value):
            return True
        return value == 0.0

    if isinstance(value, (str, int, list, dict, bool)):
        return not value

    # dict, date, datetime
    return False

def op_add(data=None, a=None, b=None, *_ignored) -> float:
    return to_number(a) + to_number(b)

def parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)

        return value

    if isinstance(value, date):
        return datetime.combine(value, time(), timezone.utc)

    value = to_string(value)

    match = DATE_PATTERN.match(value)
    if match:
        return datetime(int(match[1]), int(match[2]), int(match[3]), tzinfo=timezone.utc)

    match = DATE_TIME_PATTERN.match(value)
    if match is None:
        raise ValueError(f'illegal date-time string: {value!r}')

    year  = int(match.group('year'))
    month = int(match.group('month'))
    day   = int(match.group('day'))

    hour   = int(match.group('hour')     or 0)
    minute = int(match.group('minute')   or 0)
    second = float(match.group('second') or 0.0)

    tzsign   = match.group('tzsign') or '+'
    tzhour   = int(match.group('tzhour')   or 0)
    tzminute = int(match.group('tzminute') or 0)

    tzoff = tzhour * 60 + tzminute
    if tzsign == '-':
        tzoff = -tzoff

    int_second = int(second)
    return datetime(year, month, day, hour, minute, int_second,
        int(second * 1_000_000) - int_second * 1_000_000,
        timezone(timedelta(minutes=tzoff)))

def to_int(value: Any) -> int:
    value = to_number(value)
    if isnan(value):
        return 0
    return int(value)

def op_plus_time(data=None, dtstr=None, value=None, unit=None, *_ignored) -> datetime:
    dt = parse_time(dtstr)

    if unit == 'year':
        return dt.replace(year=dt.year + to_int(value))

    if unit == 'month':
        month  = dt.month + to_int(value)
        years  = (month - 1) // 12
        year   = dt.year + years
        month -= years * 12

        return dt.replace(year=year, month=month)

    if unit == 'day':
        return dt + timedelta(days=to_number(value))

    if unit == 'hour':
        return dt + timedelta(hours=to_number(value))

    raise ValueError(f'illegal unit: {unit!r}')

OPTIONAL_PREFIX = "URN:UVCI:"
UVCI_SPLIT = re.compile('[/#:]')

def op_extract_from_uvci(data=None, uvci=None, index=None, *_ignored) -> Optional[str]:
    index = to_int(index)
    if uvci is None or index < 0:
        return None

    uvci = to_string(uvci)
    if uvci.startswith(OPTIONAL_PREFIX):
        uvci = uvci[len(OPTIONAL_PREFIX):]

    fragments = UVCI_SPLIT.split(uvci)
    return fragments[index] if index < len(fragments) else None

def op_after(data=None, a=None, b=None, c=None, *_ignored):
    if c is None:
        return parse_time(a) > parse_time(b)

    return parse_time(a) > parse_time(b) and parse_time(b) > parse_time(c)

def op_before(data=None, a=None, b=None, c=None, *_ignored):
    if c is None:
        return parse_time(a) < parse_time(b)

    return parse_time(a) < parse_time(b) and parse_time(b) < parse_time(c)

def op_not_after(data=None, a=None, b=None, c=None, *_ignored):
    if c is None:
        return parse_time(a) <= parse_time(b)

    return parse_time(a) <= parse_time(b) and parse_time(b) <= parse_time(c)

def op_not_before(data=None, a=None, b=None, c=None, *_ignored):
    if c is None:
        return parse_time(a) >= parse_time(b)

    return parse_time(a) >= parse_time(b) and parse_time(b) >= parse_time(c)

BUILTINS: Operations = {
    '===': lambda data=None, a=None, b=None, *_ignored: a == b,
    '<':   op_less_than,
    '>':   op_greater_than,
    '<=':  op_less_than_or_equal,
    '>=':  op_greater_than_or_equal,
    '!':   lambda data=None, a=None, *_ignored: not_(a),
    '+':   op_add,
    'in':  op_in,
    'var': op_var,
    'before':     op_before,
    'not-before': op_not_before,
    'after':      op_after,
    'not-after':  op_not_after,
    'plusTime':        op_plus_time,
    'extractFromUVCI': op_extract_from_uvci,
}
