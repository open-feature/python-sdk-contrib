
VENV_NAME ?= .venv
VENV_ACTIVATE = . $(VENV_NAME)/bin/activate
PYTHON = ${VENV_NAME}/bin/python3

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Targets:"
	@echo "  requirements    Installs dependencies
	@echo "  venv            Creates a virtual environment and install dependencies"
	@echo "  test            Run pytest on the tests/ directory"
	@echo "  lint            Check code with flake8 and black"
	@echo "  format          Format code with black"

.PHONY: requirements
requirements:
	$(VENV_ACTIVATE); pip install -r requirements.txt

.PHONY: venv
venv: $(VENV_NAME)
	python3 -m venv $(VENV_NAME)
	$(VENV_ACTIVATE); pip install -r requirements.txt

.PHONY: test
test: venv ## Run pytest on the tests/ directory
	$(VENV_ACTIVATE); pytest tests/

.PHONY: lint
lint: venv ## Check code with flake8 and black
	$(VENV_ACTIVATE); flake8 .
	$(VENV_ACTIVATE); black --check .

.PHONY: format
format: venv ## Format code with black
	$(VENV_ACTIVATE); black .
