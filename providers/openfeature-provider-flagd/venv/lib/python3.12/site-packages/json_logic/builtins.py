from __future__ import annotations

from typing import Any, List, Iterable, Union
from datetime import date, datetime, time, timezone
from time import mktime
from wsgiref.handlers import format_date_time
from math import isnan
from array import array

import json
import sys

from .types import JsonValue, Operations

NAN = float('nan')
NUMERIC = (int, float)
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

def op_equals(data=None, a=None, b=None, *_ignored) -> bool:
    atype = type(a)
    if atype is type(b):
        if atype in (list, dict):
            return a is b
        return a == b

    if isinstance(a, NUMERIC):
        if isinstance(b, NUMERIC):
            return a == b
        return a == to_number(b)

    if isinstance(b, NUMERIC):
        return to_number(a) == b

    if a is None or b is None:
        return False

    if isinstance(a, str):
        if isinstance(b, bool):
            return to_number(a) == to_number(b)

        if isinstance(b, (list, dict)):
            return a == to_string(b)

        raise TypeError

    if isinstance(a, bool):
        return to_number(a) == to_number(b)

    if isinstance(a, (list, dict)):
        if isinstance(b, (list, dict)):
            return False

        if isinstance(b, str):
            return to_string(a) == b

        if isinstance(b, bool):
            return to_number(a) == to_number(b)

        raise TypeError

    raise TypeError

def to_number(a: Any) -> Union[float, int]:
    if isinstance(a, NUMERIC):
        return a

    if a is None:
        return 0

    if isinstance(a, list):
        if not a:
            return 0
        elif len(a) > 1:
            return NAN
        else:
            return to_number(a[0])

    if isinstance(a, dict):
        return NAN

    if isinstance(a, str) and a.strip().lower() in ('inf', '-inf', '+inf'):
        # Python's float() would allow these, but JavaScript won't recognize these
        return NAN

    if isinstance(a, datetime):
        return (a - EPOCH).total_seconds() * 1000.0

    if isinstance(a, date):
        return (datetime.combine(a, time()) - EPOCH).total_seconds() * 1000.0

    try:
        return float(a)
    except ValueError:
        return NAN

def to_string(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, float):
        return '%.15g' % value

    if isinstance(value, int):
        return str(value)

    if value is None:
        return 'null'

    if value is True:
        return 'true'

    if value is False:
        return 'false'

    if isinstance(value, list):
        return ','.join(to_string(item) for item in value)

    if isinstance(value, dict):
        return '[object Object]'

    if isinstance(value, (date, datetime)):
        return format_date_time(mktime(value.timetuple()))

    return str(value)

def to_bool(value: Any=None) -> bool:
    if value is None:
        return False

    if type(value) is bool:
        return value # type: ignore

    if isinstance(value, float):
        if isnan(value):
            return False
        return bool(value)

    if isinstance(value, (str, int, list, bool)):
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

    if isinstance(value, (str, int, list, bool)):
        return not value

    # dict, date, datetime
    return False

def op_add(data=None, *args: Any) -> Union[float, int]:
    value: Union[float, int] = 0
    for arg in args:
        value += to_number(arg)
    return value

def op_mul(data=None, *args: Any) -> Union[float, int]:
    value: Union[float, int] = 1
    for arg in args:
        value *= to_number(arg)
    return value

def json_default(arg: Any) -> JsonValue:
    if isinstance(arg, (date, datetime)):
        return arg.isoformat()

    argtype = type(arg)
    raise TypeError(f'unhandled type: {argtype.__module__}.{argtype.__name__}')

def op_log(data=None, arg: Any=None, *_ignored) -> Any:
    json.dump(arg, sys.stdout, default=json_default)
    sys.stdout.write('\n')
    return arg

def less_than(a, b) -> bool:
    if isinstance(a, NUMERIC):
        return a < to_number(b)

    if isinstance(b, NUMERIC):
        return to_number(a) < b

    if isinstance(a, str):
        return a < to_string(b)

    if isinstance(b, str):
        return to_string(a) < b

    return to_number(a) < to_number(b)

def op_less_than(data=None, a=None, b=None, c=None, *_ignored) -> bool:
    if c is None:
        return less_than(a, b)
    
    return less_than(a, b) and less_than(b, c)

def greater_than(a, b) -> bool:
    if isinstance(a, NUMERIC):
        return a > to_number(b)

    if isinstance(b, NUMERIC):
        return to_number(a) > b

    if isinstance(a, str):
        return a > to_string(b)

    if isinstance(b, str):
        return to_string(a) > b

    return to_number(a) > to_number(b)

def op_greater_than(data=None, a=None, b=None, c=None, *_ignored) -> bool:
    if c is None:
        return greater_than(a, b)
    
    return greater_than(a, b) and greater_than(b, c)

def less_than_or_equal(a, b) -> bool:
    if isinstance(a, NUMERIC):
        return a <= to_number(b)

    if isinstance(b, NUMERIC):
        return to_number(a) <= b

    if isinstance(a, str):
        return a <= to_string(b)

    if isinstance(b, str):
        return to_string(a) <= b

    return to_number(a) <= to_number(b)

def op_less_than_or_equal(data=None, a=None, b=None, c=None, *_ignored) -> bool:
    if c is None:
        return less_than_or_equal(a, b)
    
    return less_than_or_equal(a, b) and less_than_or_equal(b, c)

def greater_than_or_equal(a, b) -> bool:
    if isinstance(a, NUMERIC):
        return a >= to_number(b)

    if isinstance(b, NUMERIC):
        return to_number(a) >= b

    if isinstance(a, str):
        return a >= to_string(b)

    if isinstance(b, str):
        return to_string(a) >= b

    return to_number(a) >= to_number(b)

def op_greater_than_or_equal(data=None, a=None, b=None, c=None, *_ignored) -> bool:
    if c is None:
        return greater_than_or_equal(a, b)
    
    return greater_than_or_equal(a, b) and greater_than_or_equal(b, c)

def op_substr(data=None, string=None, index=None, length=None, *_ignored) -> str:
    string = to_string(string)
    index  = to_number(index)

    strlen = len(string)
    if isnan(index):
        index = 0
    elif index < 0:
        index = -index
        if index >= strlen:
            index = 0
        else:
            index = strlen - int(index)
    else:
        index = int(index)
        if index >= strlen:
            index = strlen

    if length is None:
        end_index = strlen
    else:
        length = to_number(length)
        if isnan(length):
            end_index = index
        else:
            length = int(length)
            if length < 0:
                end_index = strlen + length
                if end_index < index:
                    end_index = index
            else:
                end_index = index + length

    return string[index:end_index]

def op_substr_utf16(data=None, string=None, index=None, length=None, *_ignored) -> str:
    string = array('H', to_string(string).encode('UTF-16BE'))

    index = to_number(index)

    strlen = len(string)
    if isnan(index):
        index = 0
    elif index < 0:
        index = -index
        if index >= strlen:
            index = 0
        else:
            index = strlen - int(index)
    else:
        index = int(index)
        if index >= strlen:
            index = strlen

    if length is None:
        end_index = strlen
    else:
        length = to_number(length)
        if isnan(length):
            end_index = index
        else:
            length = int(length)
            if length < 0:
                end_index = strlen + length
                if end_index < index:
                    end_index = index
            else:
                end_index = index + length

    return string[index:end_index].tobytes().decode('UTF-16BE', errors='replace')

def op_missing(data=None, *args: Any) -> List[str]:
    keys: Iterable[Any]
    if args:
        arg0 = args[0]
        if isinstance(arg0, list):
            keys = arg0
        else:
            keys = args
    else:
        keys = args

    missing_keys: List[str] = []

    for key in keys:
        value = op_var(data, key)
        if value is None or value == '':
            missing_keys.append(key)

    return missing_keys

def op_missing_some(data=None, need_count: Any=0, keys: Any=None, *_ignored) -> List[str]:
    if not isinstance(keys, list):
        return []

    need_count = to_number(need_count)
    missing_keys = op_missing(data, keys)
    if len(keys) - len(missing_keys) >= need_count:
        return []
    
    return missing_keys

def op_var(data=None, key=None, default=None) -> Any:
    if key is None or key == '':
        return data

    if isinstance(key, NUMERIC):
        if isinstance(data, (list, str)):
            try:
                index = int(key)
            except ValueError:
                return default

            if index != key or index < 0 or index >= len(data):
                return default

            return data[index]

        elif isinstance(data, dict):
            data = data.get(key)
            if data is None:
                return default

        else:
            return default

    props: List[str] = to_string(key).split('.')

    for prop in props:
        if isinstance(data, (list, str)):
            if prop == 'length':
                # emulate JavaScript behavior
                return len(data)

            try:
                index = int(prop, 10)
            except ValueError:
                return default

            if prop != str(index) or index < 0 or index >= len(data):
                # emulate JavaScript behavior
                return default

            data = data[index]
        elif isinstance(data, dict):
            data = data.get(prop)
        else:
            return default

    if data is None:
        return default

    return data

def op_merge(data=None, *args: Any) -> List[Any]:
    items: List[Any] = []
    for arg in args:
        if isinstance(arg, list):
            items.extend(arg)
        else:
            items.append(arg)
    return items

def op_in(data=None, needle=None, haystack=None, *_ignored) -> bool:
    if isinstance(haystack, list):
        return needle in haystack
        
    if isinstance(haystack, str):
        return to_string(needle) in haystack

    return False

BUILTINS: Operations = {
    '==':  op_equals,
    '!=':  lambda data=None, a=None, b=None, *_ignored: not op_equals(data, a, b),
    '===': lambda data=None, a=None, b=None, *_ignored: a == b,
    '!==': lambda data=None, a=None, b=None, *_ignored: a != b,
    '<':   op_less_than,
    '>':   op_greater_than,
    '<=':  op_less_than_or_equal,
    '>=':  op_greater_than_or_equal,
    '!':   lambda data=None, a=None, *_ignored: not_(a),
    '!!':  lambda data=None, a=None, *_ignored: to_bool(a),
    '+':   op_add,
    '*':   op_mul,
    '-':   lambda data=None, a=None, b=None, *_ignored: -to_number(a) if b is None else to_number(a) - to_number(b),
    '/':   lambda data=None, a=None, b=None, *_ignored: to_number(a) / to_number(b),
    '%':   lambda data=None, a=None, b=None, *_ignored: to_number(a) % to_number(b),
    'in':  op_in,
    'min': lambda data=None, *args: min(to_number(arg) for arg in args) if args else NAN,
    'max': lambda data=None, *args: max(to_number(arg) for arg in args) if args else NAN,
    'cat': lambda data=None, *args: ''.join(to_string(arg) for arg in args),
    'log': op_log,
    'var': op_var,
    'substr':       op_substr,
    'merge':        op_merge,
    'missing':      op_missing, # type: ignore
    'missing_some': op_missing_some,
}
