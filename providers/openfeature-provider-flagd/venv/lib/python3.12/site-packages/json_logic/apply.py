from typing import Dict

from .types import JsonValue, Operations
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

    if op == 'if' or op == '?:':
        argc = len(args)

        last_index = argc - 1
        index = 0
        while index < last_index:
            if to_bool(apply(args[index], data, operations)):
                index += 1
                if index >= argc:
                    return None

                return apply(args[index], data, operations)
            index += 2

        if index >= argc:
            return None

        return apply(args[index], data, operations)

    elif op == 'and':
        current = None
        for arg in args:
            current = apply(arg, data, operations)
            if not_(current):
                return current
        return current

    elif op == 'or':
        current = None
        for arg in args:
            current = apply(arg, data, operations)
            if to_bool(current):
                return current
        return current

    elif op == 'filter':
        if len(args) < 2:
            return []

        items = apply(args[0], data, operations)
        if not isinstance(items, list):
            return []

        sublogic = args[1]

        filtered = [item for item in items if to_bool(apply(sublogic, item, operations))]
        return filtered

    elif op == 'reduce':
        argc = len(args)
        if argc < 1:
            return None

        items    = apply(args[0], data, operations)
        sublogic = args[1] if argc > 1 else None
        init     = args[2] if argc > 2 else None

        if not isinstance(items, list):
            return init

        context: Dict[str, JsonValue] = {'accumulator': init}
        for item in items:
            context['current']     = item
            context['accumulator'] = apply(sublogic, context, operations)

        return context['accumulator']

    elif op == 'map':
        argc = len(args)
        if argc < 1:
            return []

        items = apply(args[0], data, operations)
        if not isinstance(items, list):
            return []

        sublogic = args[1] if argc > 1 else None
        mapped = [apply(sublogic, item, operations) for item in items]
        return mapped

    elif op == 'all':
        # yes, JsonLogic defines that all of an empty list is False
        if len(args) < 2:
            return False

        items = apply(args[0], data, operations)
        if not isinstance(items, list) or not items:
            return False

        sublogic = args[1]
        return all(to_bool(apply(sublogic, item, operations)) for item in items)

    elif op == 'some':
        if len(args) < 2:
            return False

        items = apply(args[0], data, operations)
        if not isinstance(items, list):
            return False

        sublogic = args[1]
        return any(to_bool(apply(sublogic, item, operations)) for item in items)

    elif op == 'none':
        if len(args) < 2:
            return True

        items = apply(args[0], data, operations)
        if not isinstance(items, list):
            return True

        sublogic = args[1]
        return not any(to_bool(apply(sublogic, item, operations)) for item in items)

    args = [apply(arg, data, operations) for arg in args]

    if op in operations:
        return operations[op](data, *args) # type: ignore
    elif '.' in op:
        props = op.split('.')
        ops = operations
        for index, prop in enumerate(props):
            if isinstance(ops, dict) and prop not in ops:
                raise ReferenceError(f"Unrecognized operation: {'.'.join(props[:index + 1])!r}")
            ops = ops[prop] # type: ignore
        return ops(data, *args) # type: ignore

    raise ReferenceError(f"Unrecognized operation: {op!r}")
