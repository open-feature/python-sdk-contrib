from . import certLogic
from ..builtins import json_default

if __name__ == '__main__':
    import sys
    import json

    logic  = json.loads(sys.argv[1]) if len(sys.argv) > 1 else None
    data   = json.loads(sys.argv[2]) if len(sys.argv) > 2 else None
    result = certLogic(logic, data)
    json.dump(result, sys.stdout, default=json_default)
    sys.stdout.write('\n')
