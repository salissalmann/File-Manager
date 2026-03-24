VENV := /tmp/filemanager_venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

# Default input/output paths
LEDGER := inputs/1523 TEST Ledger.xlsx
FILES := inputs/filenames.txt
OUTPUT := outputs/results.xlsx
BASE_PATH :=

.PHONY: help install test run clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

test: ## Run all tests (161 tests)
	$(PYTEST) tests/ -v

test-quick: ## Run tests without verbose output
	$(PYTEST) tests/

run: ## Run matching with default test data
	$(PYTHON) main.py --ledger "$(LEDGER)" --files "$(FILES)" --output "$(OUTPUT)" --base-path "$(BASE_PATH)"

clean: ## Remove output files and cache
	rm -rf outputs/*.xlsx __pycache__ .pytest_cache tests/__pycache__ src/__pycache__ src/**/__pycache__

# ─── Examples ───────────────────────────────────────────────────
# make install              # first-time setup
# make test                 # run all 161 tests
# make run                  # run with default test data
# make run LEDGER=path/to/ledger.xlsx FILES=path/to/files.txt OUTPUT=out.xlsx
# make run BASE_PATH="https://company.sharepoint.com/sites/docs/files"
