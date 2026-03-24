# MATCH — File-to-Ledger Matching Engine

## Quick Start

```bash
make install   # one-time setup
make test      # run all 161 tests
make run       # run matching on test data
```

Custom paths:
```bash
make run LEDGER=path/to/ledger.xlsx FILES=path/to/files.txt OUTPUT=out.xlsx
```

With clickable file links (SharePoint or local folder):
```bash
make run BASE_PATH="https://company.sharepoint.com/sites/docs/files"
```

Or directly:
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/filenames.txt --output outputs/results.xlsx --base-path "https://sharepoint.example.com/files"
```

---

## How It Works (High-Level)

- **Input:** A ledger Excel file (rows with vendor, date, CA code, amount) + a list of PDF filenames
- **Step 1 — Parse filenames:** Each filename is broken into structured fields (vendor name, CA code, dollar amounts, dates, invoice numbers) using pattern recognition. Handles messy real-world formats like `"Inv 1199 Ck 1081 REstan Drywall Ca 53615"` or `"$17000 and $8500"`
- **Step 2 — Score every pair:** Each ledger row is compared against every file. Points are awarded for matching amount (50pts), CA code (30pts), and vendor name (20pts via fuzzy matching). Total score = 0-100
- **Step 3 — Veto bad matches:** Even if a file scores high, it gets rejected if it contains the *wrong* CA code or *wrong* amount. Key rule: missing data is neutral, wrong data is a hard reject
- **Step 4 — Assign 1:1:** Best-scoring pairs are assigned first (greedy). Duplicate ledger rows (e.g. two $5,000 entries) each get a different file. Multi-amount files (e.g. `"$17000 and $8500"`) can match two rows
- **Step 5 — Partial payment check:** For unmatched rows sharing the same vendor + CA, checks if their amounts *sum* to a file's amount (split-payment detection)
- **Step 6 — Classify:** Strong (score >= 80), Good (>= 50), Review (low/ambiguous), No Match
- **Output:** Excel file with 4 sheets — Summary, Match Results (color-coded with confidence scores, match reasoning, clickable file links, and top alternative candidates), Orphan Files, and Veto Log

**Result on test data:** 80.8% match rate (16 Strong, 5 Good, 2 Review, 3 No Match) across 26 ledger rows and 29 files. 161 automated tests covering all edge cases.

---

## Example Commands (Demo Scenarios)

Each scenario file isolates a specific matching feature so you can verify it independently. All use the same 26-row ledger.

> **Note:** Activate the virtualenv first: `source /tmp/filemanager_venv/bin/activate`
> Or prefix each command with `/tmp/filemanager_venv/bin/python` instead of `python`.

### 1. Full run — all 29 files against all 26 ledger rows
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/filenames.txt --output outputs/results.xlsx
```
**Expected:** 16 Strong, 5 Good, 2 Review, 3 No Match, 6 orphans. Open `outputs/results.xlsx` → Summary sheet shows 80.8% match rate.

### 2. Veto rules — CA mismatch + amount conflict rejections
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/scenario_veto.txt --output outputs/veto_demo.xlsx
```
**Expected:** Row 1 (Westheimer, CA 50408) matches the correct-CA file, rejects `ca99999 wrongca` file. Row 5 (Ferguson, $4520) matches $4520 file, rejects `$9999 wrongamount` file. Check the **Veto Log** sheet for rejection reasons.

### 3. Near-amount tolerance — $1345 vs $1345.50, $445.04 vs $445.06
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/scenario_near_amounts.txt --output outputs/near_amounts.xlsx
```
**Expected:** City Electric $1345 matches file with $1345.50 (within $1.00 tolerance). Lowes $445.04 matches file with $445.06. Both show `amount_near` in the Match Reason column.

### 4. Duplicate row 1:1 assignment — ABC Supply $5k x2, VYO $6k x2
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/scenario_duplicates.txt --output outputs/duplicates.xlsx
```
**Expected:** Two ABC Supply $5,000 rows each get a *different* file (`partial.pdf` vs `partial second.pdf`). Two VYO $6,000 rows each get a different file (`part1.pdf` vs `part2.pdf`). No file is double-assigned.

### 5. Multi-amount files — "$17000 and $8500" matching two rows
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/scenario_multi_amount.txt --output outputs/multi_amount.xlsx
```
**Expected:** The file `$17000 and $8500 jb1523.pdf` can match **two** ledger rows (one for $17k, one for $8.5k). Single-amount files are preferred over the multi-amount file (multi-amount gets a -5 penalty).

### 6. Invoice/vendor-only — "Inv 1199", bare decimals, unparseable orphans
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/scenario_invoice_vendor.txt --output outputs/invoice_vendor.xlsx
```
**Expected:** REstan Drywall matches `Inv 1199` file (vendor + CA + invoice hint = score 55). Houston Permitting matches bare `80.63` (no $ sign). `20211206_161057` is an orphan (unparseable). Pot-O-Gold gets Review status (vendor-only match).

### 7. Clickable SharePoint links in Excel
```bash
python main.py --ledger "inputs/1523 TEST Ledger.xlsx" --files inputs/filenames.txt --output outputs/with_links.xlsx --base-path "https://company.sharepoint.com/sites/docs"
```
**Expected:** Open `outputs/with_links.xlsx` → the **File Path** column (G) contains clickable blue hyperlinks pointing to `https://company.sharepoint.com/sites/docs/<filename>`.

### 8. Run all 161 tests
```bash
python -m pytest tests/ -v
```
**Expected:** 161 passed in ~0.7s. Covers: filename parsing (49), ledger parsing (12), scoring (25), veto rules (15), matcher (17), integration (38), Excel output (8).

---

## Approach

### 1. Filename Parsing

Each filename is parsed into structured fields using regex-based extraction. The parser handles multiple formats found in real-world filenames:

| Field | Formats handled | Example |
|-------|----------------|---------|
| Date | `M.DD.YYYY`, `MM-DD-YYYY`, `YYYYMMDD_HHMMSS` | `3.15.2023`, `12-21-2022` |
| CA code | `ca50408`, `Ca 53615`, `CA60110` | Requires `ca` prefix — `jb1523` is NOT a CA code |
| Amount | `$17000`, `$222.77`, `$17000 and $8500`, bare `80.63` | Dollar sign or fallback decimal |
| Invoice | `Inv 1199`, `Inv 113022-01` | `Inv` prefix prevents treating as amount |
| Job # | `jb1523`, `Jb 1523` | Stripped from vendor name |

Key parsing decisions:
- `Inv 1199` is an invoice number, **not** `$1,199` — the `Inv` prefix is detected first
- `jb1523` is a job number, **not** CA code 1523 — the `jb` prefix is distinguished from `ca`
- `$99.99` and `$9999` are preserved as distinct amounts (Decimal, not string comparison)
- Multi-amount files (`$17000 and $8500`) are split and stored as multiple amounts

### 2. Scoring Engine

Each ledger row is scored against every file using weighted signals:

| Signal | Points | Condition |
|--------|--------|-----------|
| Amount exact match | 50 | Ledger amount found in file amounts |
| Amount near match | 40 | Within $1.00 or 0.5% tolerance |
| CA code match | 30 | Ledger CA found in file CA codes |
| Vendor match (strong) | 20 | Fuzzy ratio >= 85% |
| Vendor match (partial) | 10 | Fuzzy ratio >= 65% |
| Invoice hint (tie-breaker) | 5 | Ledger amount appears in file invoice numbers |
| Multi-amount penalty | -5 | File has >1 amount (ambiguity deduction) |

Maximum score: 100. Vendor matching uses `rapidfuzz` with prefix stripping ("THE HOME DEPOT" matches "home depot").

### 3. Veto Rules

Even high-scoring matches are rejected if:

| Veto Rule | Condition | Principle |
|-----------|-----------|-----------|
| **CA mismatch** | File HAS CA code(s), but none match ledger CA | Presence of wrong data = reject |
| **Amount conflict** | File HAS amount(s), but none within tolerance | Presence of wrong data = reject |
| **Vendor mismatch** | File vendor similarity < 45% | Clearly different vendor = reject |

**Key principle: absence of data is neutral (lowers confidence); presence of WRONG data is a veto.**

- File has no CA code → no veto (could belong to any CA)
- File has CA 99999 but ledger expects CA 50408 → **VETO**

### 4. 1:1 Assignment + Partial Payment Sum Matching

After scoring and veto, a greedy algorithm assigns files to ledger rows:

1. Sort all valid (row, file, score) candidates by score descending
2. Assign highest-scoring pair first, remove both from pool
3. Multi-amount files (e.g., `$17000 and $8500`) can match up to N rows where N = number of amounts
4. Duplicate filenames are tracked by index (handles identical filenames correctly)

**Second pass — Partial payment sum matching:**
For unmatched rows that share the same vendor + CA code, the engine checks if their amounts sum to a file amount. Example: two rows of $3,000 and $7,000 from the same vendor/CA can match a file showing $10,000.

### 5. Classification

| Status | Criteria |
|--------|----------|
| **Strong** | Score >= 80 (amount + CA + vendor) |
| **Good** | Score >= 50 |
| **Review** | Score > 0 but low or ambiguous (includes near-ties) |
| **No Match** | Score = 0 or all candidates vetoed |

---

## Test Data Results

### Summary

| Metric | Count |
|--------|-------|
| Total ledger rows | 26 |
| Strong matches | 16 |
| Good matches | 5 |
| Needs review | 2 |
| No match | 3 |
| Orphan files | 6 |
| **Match rate** | **80.8%** |

### Detailed Results

| Row | Vendor | CA | Amount | Matched File | Score | Status | Reason |
|-----|--------|----|--------|-------------|-------|--------|--------|
| 1 | WESTHEIMER PLUMBING | 50408 | $17,000 | westheimer plumbing ca50408 $17000 | 100 | Strong | amount + CA + vendor |
| 2 | WESTHEIMER PLUMBING | 50408 | $8,500 | westheimer plumbing ca50408 $8500 | 100 | Strong | amount + CA + vendor |
| 3 | THE HOME DEPOT | 50408 | $222.77 | home depot $222.77 | 70 | Good | amount + vendor (no CA in file) |
| 4 | THE HOME DEPOT | 50412 | $118.42 | home depot $118.42 | 70 | Good | amount + vendor (no CA in file) |
| 5 | Ferguson | 60110 | $4,520 | ferguson ca60110 $4520 | 100 | Strong | amount + CA + vendor |
| 6 | Ferguson | 60110 | $260 | — | 0 | No Match | No file has $260 |
| 7 | ABC Supply | 51010 | $10,000 | abc supply ca51010 $10000 | 100 | Strong | amount + CA + vendor |
| 8 | ABC Supply | 51010 | $5,000 | abc supply ca51010 $5000 partial | 100 | Strong | 1:1 assigned |
| 9 | ABC Supply | 51010 | $5,000 | abc supply ca51010 $5000 partial second | 100 | Strong | 1:1 assigned |
| 10 | City Electric | 70220 | $1,345 | city electric ca70220 $1345 | 100 | Strong | exact amount match |
| 11 | City Electric | 70220 | $1,345 | city electric ca70220 $1345.50 | 90 | Strong | near amount ($0.50 off) |
| 12 | Lowes | 1523 | $890.12 | lowes ca1523 $890.12 | 100 | Strong | amount + CA + vendor |
| 13 | Lowes | 1523 | $445.04 | lowes ca1523 $445.06 | 90 | Strong | near amount ($0.02 off) |
| 14 | VYO Structural | 80100 | $12,000 | vyo structural ca80100 $12000 | 100 | Strong | amount + CA + vendor |
| 15 | VYO Structural | 80100 | $6,000 | vyo structural ca80100 $6000 part1 | 100 | Strong | 1:1 assigned |
| 16 | VYO Structural | 80100 | $6,000 | vyo structural ca80100 $6000 part2 | 100 | Strong | 1:1 assigned |
| 17 | Random Vendor | 99999 | $999.99 | random vendor ca99999 $999.99 | 100 | Strong | amount + CA + vendor |
| 18 | WESTHEIMER PLUMBING | 99999 | $17,000 | westheimer plumbing ca99999 $17000 | 100 | Strong | Correct CA 99999 match |
| 19 | HOME DEPOT | 99999 | $222.77 | home depot $222.77 ca99999 | 100 | Strong | Correct CA 99999 match |
| 20 | Ferguson | 60110 | $99.99 | — | 0 | No Match | No file has $99.99 |
| 21 | REstan Drywall | 53615 | $1,199 | Inv 1199 REstan Drywall Ca 53615 | 55 | Good | vendor + CA + invoice hint |
| 22 | Marin Construction | 51070 | $5,600 | Inv 113022-01 Marin Construction Ca 51070 | 50 | Good | vendor + CA (no amount in file) |
| 23 | Houston Permitting | 55000 | $80.63 | Houston Permitting - 80.63 | 70 | Good | vendor + amount (no CA in file) |
| 24 | Pot-O-Gold | 50500 | $250 | pot-o-gold invoice - reprint | 20 | Review | vendor only — no amount, CA, or date |
| 25 | Unknown Vendor | 56000 | $1,500 | — | 0 | No Match | No matching file exists |
| 26 | Pot-O-Gold | 50500 | $300 | pot-o-gold invoice - reprint | 20 | Review | vendor only — no amount, CA, or date |

### Veto Rules in Action

| Ledger Row | Rejected File | Veto Reason |
|-----------|---------------|-------------|
| Row 1 (Westheimer, CA 50408) | westheimer ca99999 $17000 | CA mismatch: file has 99999, ledger expects 50408 |
| Row 3 (Home Depot, CA 50408) | home depot $222.77 ca99999 | CA mismatch: file has 99999, ledger expects 50408 |
| Row 5 (Ferguson, $4520) | ferguson ca60110 $9999 | Amount conflict: file has $9999, ledger expects $4520 |
| Row 6 (Ferguson, $260) | ferguson ca60110 $2260 | Amount conflict: $2260 vs $260 (769% difference) |

### Edge Cases Handled

| Edge Case | How It's Handled |
|-----------|-----------------|
| `Inv 1199` looks like $1,199 | Invoice prefix detected first — extracted as invoice number, not amount |
| `jb1523` looks like CA 1523 | Job number prefix `jb` distinguished from CA prefix `ca` |
| `$99.99` vs `$9999` | Decimal-aware Decimal comparison, not string matching |
| `$1345` vs `$1345.50` | Within $1.00 tolerance — accepted as near-match |
| `$445.04` vs `$445.06` | Within $1.00 tolerance — accepted as near-match |
| `$260` vs `$2260` | 769% difference — vetoed, too far apart |
| Two ABC Supply $5000 rows | 1:1 greedy assignment gives each row a different file |
| Two identical pot-o-gold filenames | Tracked by file index, each assigned to a different row |
| `THE HOME DEPOT` vs `home depot` | Prefix stripping + case-insensitive fuzzy matching |
| `20211206_161057` (unparseable) | Extracted date only; no vendor/amount/CA — orphan file |
| `Houston Permitting - 80.63` (no $) | Bare decimal fallback when no $ amounts found |
| Multi-amount file `$17000 and $8500` | Both amounts indexed; file can match two ledger rows |

---

## Test Coverage

161 tests across 7 test files:

| Test File | Tests | What's Tested |
|-----------|-------|---------------|
| `test_filename_parser.py` | 49 | All date/CA/amount/invoice/vendor extraction edge cases |
| `test_ledger_parser.py` | 12 | Excel parsing, field types, decimal precision |
| `test_scorer.py` | 25 | Amount/CA/vendor scoring, invoice tie-breaker, multi-amount penalty |
| `test_veto.py` | 15 | CA mismatch, amount conflict, vendor mismatch, multi-amount |
| `test_matcher.py` | 17 | 1:1 assignment, multi-amount, partial payment sums, alternatives |
| `test_integration.py` | 38 | Full end-to-end: every row's expected status, veto actions, orphans |
| `test_excel_writer.py` | 8 | Excel sheet structure, file paths, hyperlinks, alternatives column |

```bash
make test  # runs all 161 tests in ~0.7s
```

---

## Output

The Excel output (`outputs/results.xlsx`) contains 4 sheets:

1. **Summary** — Match rate, status counts
2. **Match Results** — Each ledger row with matched file, score, confidence, match reason, status (color-coded), file path with clickable hyperlink, and top alternative candidates
3. **Orphan Files** — Files that matched no ledger row (with parsed fields)
4. **Veto Log** — Every rejected match with the specific veto reason

### Match Results Columns

| Column | Description |
|--------|-------------|
| Row # | Ledger row number |
| Vendor | Ledger vendor name |
| Date | Ledger date |
| CA Code | Ledger CA account code |
| Amount | Ledger amount |
| Matched File | Name of the best matching file |
| File Path | Full path/URL (clickable hyperlink when `--base-path` is set) |
| Score | 0-100 match score |
| Confidence | 0%-100% confidence percentage |
| Match Reason | Which signals matched (e.g., "amount_exact + ca_match + vendor_match") |
| Status | Strong / Good / Review / No Match (color-coded) |
| Veto Info | Why the top rejected candidate was vetoed |
| Alternatives | Top 2-3 runner-up candidates with scores and reasons |

---

## Configuration

All weights and thresholds are in `config.py` and can be adjusted:

```python
AMOUNT_EXACT_WEIGHT = 50    # points for exact amount match
AMOUNT_NEAR_WEIGHT = 40     # points for near-amount (within tolerance)
AMOUNT_SUM_WEIGHT = 35      # points for partial payment sum match
CA_MATCH_WEIGHT = 30        # points for CA code match
VENDOR_STRONG_WEIGHT = 20   # points for strong vendor match (>= 85% fuzzy)
INVOICE_MATCH_WEIGHT = 5    # points for invoice number tie-breaker
MULTI_AMOUNT_PENALTY = 5    # deducted when file has >1 amount (ambiguity)
AMOUNT_ABS_TOLERANCE = 1.00 # $1.00 absolute tolerance
AMOUNT_REL_TOLERANCE = 0.5% # relative tolerance
```
