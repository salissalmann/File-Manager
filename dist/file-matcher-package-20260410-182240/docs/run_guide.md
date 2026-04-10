# File Matcher Run Guide (Non-Technical)

This guide shows how to run the system end-to-end with your own inputs.

## 1) One-time setup

Open Terminal in the project folder, then run:

```bash
make install
```

This creates a local Python environment and installs required packages.

### If you do not have `make` (common on Windows), use:

```bash
python -m venv .venv
```

Install dependencies:

- Windows (PowerShell):

```powershell
.venv\Scripts\pip install -r requirements.txt
```

- Mac/Linux:

```bash
.venv/bin/pip install -r requirements.txt
```

## 2) Where to put files

- Put your ledger Excel file in: `inputs/`
- Put your file list CSV in: `inputs/`

Recommended names:
- Ledger: `inputs/Milford-Ledger Clean.xlsx`
- File list: `inputs/dropbox_files.csv`

You can use different names too (see step 4).

## 3) File list CSV format

Use a CSV with at least:
- `Filename` (required)
- `Path` (optional but recommended for link output)

Example:

```csv
Filename,Path
12.10.2021 VYO CA 50405 $17930 Invoice 0000077.pdf,/Shared Documents/...
Ring.png,/Shared Documents/...
```

## 4) Run matching

### Default run (uses default names above)

```bash
make run
```

No-`make` alternative:

- Windows (PowerShell):

```powershell
.venv\Scripts\python main.py --ledger "inputs/Milford-Ledger Clean.xlsx" --files "inputs/dropbox_files.csv" --output "outputs/results.xlsx"
```

- Mac/Linux:

```bash
.venv/bin/python main.py --ledger "inputs/Milford-Ledger Clean.xlsx" --files "inputs/dropbox_files.csv" --output "outputs/results.xlsx"
```

### Custom run (if your file names are different)

```bash
make run LEDGER="inputs/MyLedger.xlsx" FILES="inputs/my_file_list.csv" OUTPUT="outputs/results.xlsx"
```

## 5) Where outputs are generated

After each run:

- Excel results: `outputs/results.xlsx`
- HTML report (clickable links + summary): `outputs/results_report.html`

## 6) Update inputs and rerun

When you have a new month/week:

1. Replace ledger file in `inputs/`
2. Replace file list CSV in `inputs/`
3. Run `make run` again
4. Open `outputs/results.xlsx`

No code changes are needed for normal refreshes.

## 7) Conservative matching behavior (current)

The engine is intentionally strict to avoid false positives:

- Amount tolerance: `0.01` dollars (penny-only)
- Vendor veto threshold: `65`
- If ledger has a vendor but filename has no vendor text, candidate is vetoed
- Veto-side vendor similarity uses stricter logic (includes `token_set_ratio`, not `partial_ratio`)

Effect: more rows can land in `Review`/`No Match`, but obvious bad matches are reduced.

## 8) Tune thresholds (optional)

Edit `config.py`:

- `AMOUNT_ABS_TOLERANCE`
  - Lower = stricter amounts
  - Higher = more amount matches
- `VENDOR_VETO_THRESHOLD`
  - Higher = stricter vendor mismatch blocking
  - Lower = more lenient vendor acceptance
- `VENDOR_STRONG_THRESHOLD`, `VENDOR_PARTIAL_THRESHOLD`
  - Affects vendor score strength in ranking/classification

After any config change, rerun:

```bash
make test-quick
make run
```

## 9) Quick troubleshooting

- Missing Python packages:
  - Run `make install` again
- Wrong input path:
  - Use custom `make run LEDGER=... FILES=...`
- Empty output:
  - Check CSV has a `Filename` column and non-empty rows

## 10) Easy handoff package

To create a zip package for another machine/user:

```bash
make package
```

No-`make` alternative:

```bash
python scripts/package_release.py
```

This creates `dist/file-matcher-package-<timestamp>.zip` with:
- code
- docs
- inputs folder (without heavy raw files)
- outputs folder
- setup instructions
