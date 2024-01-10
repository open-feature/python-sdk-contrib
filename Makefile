VENV_NAME ?= .venv
VENV_ACTIVATE = . $(VENV_NAME)/bin/activate

.DEFAULT_GOAL := help

.PHONY: init
init: venv

.PHONY: help
help:
	@echo "Targets:"
	@echo "  requirements    Installs dependencies"
	@echo "  venv            Creates a virtual environment and install dependencies"
	@echo "  test            Run pytest on the tests/ directory"
	@echo "  lint            Check code with ruff"
	@echo "  format          Format code with ruff-format"

.PHONY: requirements
requirements:
	$(VENV_ACTIVATE); pip install -r requirements.txt

.PHONY: grpc
grpc:
	$(VENV_ACTIVATE); cd schemas && buf generate buf.build/open-feature/flagd --template protobuf/buf.gen.python.yaml
	rm -rf openfeature/contrib/providers/flagd/proto
	mv proto/python openfeature/contrib/providers/flagd/proto
	sed -i.bak 's/^from schema.v1 import/from . import/' openfeature/contrib/providers/flagd/proto/schema/v1/*.py
	rm openfeature/contrib/providers/flagd/proto/schema/v1/*.bak
	rmdir proto

.PHONY: venv
venv: $(VENV_NAME)
	test -d $(VENV_NAME) || python3 -m venv $(VENV_NAME)
	$(VENV_ACTIVATE); pip install -r requirements.txt

.PHONY: test
test: venv ## Run pytest on the tests/ directory
	$(VENV_ACTIVATE); pytest tests/

.PHONY: lint
lint: venv ## Check code with ruff
	$(VENV_ACTIVATE); pre-commit run -a

.PHONY: format
format: venv ## Format code with black
	$(VENV_ACTIVATE); pre-commit run -a ruff-format
