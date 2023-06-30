
VENV_NAME ?= venv
VENV_ACTIVATE = . $(VENV_NAME)/bin/activate
PYTHON = ${VENV_NAME}/bin/python3

.DEFAULT_GOAL := help

.PHONY: help
help:
	@echo "Targets:"
	@echo "  requirements    Compiles requirements.in into requirements.txt"
	@echo "  venv            Creates a virtual environment and install dependencies"
	@echo "  test            Run pytest on the tests/ directory"
	@echo "  lint            Check code with flake8 and black"
	@echo "  format          Format code with black"

.PHONY: requirements
requirements: ## Compiles requirements.in into requirements.txt
	$(VENV_ACTIVATE); pip install pip-tools
	$(VENV_ACTIVATE); pip-compile requirements.in

.PHONY: venv
venv: $(VENV_NAME)/bin/activate ## Creates a virtual environment and install dependencies
$(VENV_NAME)/bin/activate: requirements.txt
	test -d $(VENV_NAME) || virtualenv -p python3 $(VENV_NAME)
	$(VENV_ACTIVATE); pip install -U pip setuptools
	$(VENV_ACTIVATE); pip install -r requirements.txt
	touch $(VENV_NAME)/bin/activate

.PHONY: test
test: venv ## Run pytest on the tests/ directory
	$(VENV_ACTIVATE); pytest tests/

.PHONY: lint
lint: venv ## Check code with flake8 and black
	$(VENV_ACTIVATE); flake8 src/
	$(VENV_ACTIVATE); black --check src/

.PHONY: format
format: venv ## Format code with black
	$(VENV_ACTIVATE); black src/
