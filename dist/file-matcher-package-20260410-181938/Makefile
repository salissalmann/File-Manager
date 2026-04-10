# Project-local venv (run `make install` once). Override: make install VENV=venv
VENV := .venv
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

# Default input/output paths
LEDGER := inputs/Milford-Ledger Clean.xlsx
FILES := inputs/dropbox_files.csv
OUTPUT := outputs/results.xlsx
BASE_PATH :=

.PHONY: help install setup-dropbox test run clean web-install web-dev web-kill frontend-kill web-state fetch-files fetch-dropbox package

help: ## Show this help
	@echo "Tip: type the full target on one line (e.g. \033[36mmake web-dev\033[0m), not \`make\` then \`web-dev\`."
	@echo "     \`make: No rule to make target '#'\` → a \`#\` was passed as a target; put comments after \`&&\` or on their own line."
	@echo "     One-shot Dropbox CSV: \033[36mmake setup-dropbox\033[0m (venv + pip + fetch; large download)."
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install dependencies
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

setup-dropbox: install fetch-dropbox ## After clone: venv + pip + inputs/dropbox_files.csv (long run)

test: ## Run all tests (pytest tests/ -v; see pytest --collect-only for count)
	$(PYTEST) tests/ -v

test-quick: ## Run tests without verbose output
	$(PYTEST) tests/

run: ## Run matcher; writes Excel + results_report.html (Excel / Google Sheets buttons + links)
	$(PYTHON) main.py --ledger "$(LEDGER)" --files "$(FILES)" --output "$(OUTPUT)" --base-path "$(BASE_PATH)"

clean: ## Remove output files and cache
	rm -rf outputs/*.xlsx outputs/*.csv __pycache__ .pytest_cache tests/__pycache__ src/__pycache__ src/**/__pycache__

fetch-files: ## Fetch filenames from real SharePoint API
	$(PYTHON) scripts/fetch_sharepoint_files.py

fetch-dropbox: ## Fetch filenames from Dropbox shared folder (no auth)
	$(PYTHON) scripts/fetch_dropbox_files.py

web-install: ## Install Next.js dashboard dependencies
	cd web && npm install

web-dev: ## Run dashboard (npm run dev in web/)
	cd web && npm run dev

web-kill frontend-kill: ## Force-stop dashboard dev server (SIGKILL on port 3000)
	@if lsof -ti :3000 >/dev/null 2>&1; then \
		lsof -ti :3000 | xargs kill -9; \
		echo "Killed process(es) on port 3000."; \
	else \
		echo "No process listening on port 3000."; \
	fi

web-state: ## Regenerate outputs/web_state.json for the dashboard
	$(PYTHON) scripts/build_web_state.py

package: ## Build a handoff zip package in dist/
	chmod +x scripts/package_release.sh
	./scripts/package_release.sh

# ─── Examples ───────────────────────────────────────────────────
# make install              # first-time setup
# make test                 # run full pytest suite
# make run                  # run with default test data
# make run LEDGER=path/to/ledger.xlsx FILES=path/to/files.txt OUTPUT=out.xlsx
# make run BASE_PATH="https://company.sharepoint.com/sites/docs/files"
