#!/bin/bash

set -e

buf generate buf.build/open-feature/flagd --template buf.gen.python.yaml
sed -i.bak 's/^from schema.v1 import/from . import/' proto/schema/v1/*.py
rm proto/schema/v1/*.bak
