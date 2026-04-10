# MATCH — File-to-Ledger Matching Engine

A Python-based system to match file names (e.g., invoices, receipts) to ledger entries based on amounts, CA codes, and vendor names.

## Documentation

- **[Matching engine — implementation, examples, architecture, tests](docs/matching_engine.md)** — Full pipeline (parse → score → veto → assign → classify), configuration, CLI, and test map.
- **[Run guide (non-technical)](docs/run_guide.md)** — Step-by-step input update, rerun, outputs, and packaging instructions.

## Quick Start

```bash
make install   # one-time setup (venv + pip)
make test      # run full pytest suite (pytest tests/ -v)
make run       # run matching on default ledger + file list from Makefile
make package   # build a handoff zip in dist/
```

No-`make` option (Windows/Mac/Linux):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py --ledger "inputs/Milford-Ledger Clean.xlsx" --files "inputs/dropbox_files.csv" --output "outputs/results.xlsx"
```

On Windows PowerShell, replace `.venv/bin/...` with `.venv\Scripts\...`.

To see how many tests are collected:

```bash
pytest tests/ --collect-only -q
```
