#!/bin/bash

set -e

buf generate buf.build/open-feature/flagd --template schemas/protobuf/buf.gen.python.yaml --output schemas
rm -rf openfeature/contrib/provider/flagd/proto
sed -i.bak 's/^from schema.v1 import/from . import/' proto/python/schema/v1/*.py
rm proto/python/schema/v1/*.bak
mv proto/python src/openfeature/contrib/provider/flagd/proto
rmdir proto
