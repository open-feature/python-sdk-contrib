from typing import Dict

from ..types import JsonValue, Operations
from .builtins import BUILTINS, to_bool, not_

def apply(logic: JsonValue, data: JsonValue=None, operations: Operations=BUILTINS) -> JsonValue:
    if isinstance(logic, list):
        return [apply(item, data, operations) for item in logic]

    if not isinstance(logic, dict) or len(logic) != 1:
        return logic

    op: str = next(iter(logic))
    args = logic[op]

    if not isinstance(args, list):
        args = [args]

    if op == 'if':
        argc = len(args)
        if argc < 1:
            return None

        if to_bool(apply(args[0], data, operations)):
            if argc < 2:
                return None
            return apply(args[1], data, operations)
        else:
            if argc < 3:
                return None
            return apply(args[2], data, operations)

    elif op == 'and':
        current = None
        for arg in args:
            current = apply(arg, data, operations)
            if not_(current):
                return current
        return current

    elif op == 'reduce':
        argc = len(args)
        if argc < 1:
            return None

        items    = apply(args[0], data, operations)
        sublogic = args[1] if argc > 1 else None
        init     = args[2] if argc > 2 else None

        if not isinstance(items, list):
            return init

        context: Dict[str, JsonValue] = {
            'accumulator': init,
            'data':        data,
        }
        for item in items:
            context['current']     = item
            context['accumulator'] = apply(sublogic, context, operations)

        return context['accumulator']

    args = [apply(arg, data, operations) for arg in args]

    if op in operations:
        return operations[op](data, *args) # type: ignore
    elif '.' in op:
        props = op.split('.')
        ops = operations
        for index, prop in enumerate(props):
            if isinstance(ops, dict) and prop not in ops:
                raise ReferenceError(f"Unrecognized operation {'.'.join(props[:index + 1])}")
            ops = ops[prop] # type: ignore
        return ops(data, *args) # type: ignore

    raise ReferenceError(f"Unrecognized operation {op}")
