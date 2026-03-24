# MATCH — File-to-Ledger Matching Engine

A Python-based system to match file names (e.g., invoices, receipts) to ledger entries based on amounts, CA codes, and vendor names.

## Documentation

All documentation has been organized into the `docs/` folder:

- [**Getting Started**](docs/getting_started.md) — Installation, tests, and running the engine.
- [**Solution Overview**](docs/matching_engine_overview.md) — Algorithm details, scoring engine, veto rules, and architecture.

## Quick Start

```bash
make install   # one-time setup
make test      # run all 161 tests
make run       # run matching on test data
```
