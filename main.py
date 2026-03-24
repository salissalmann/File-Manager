"""CLI entry point for the file-to-ledger matching engine."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.engine.matcher import run_matching
from src.output.excel_writer import write_results
from src.parsers.ledger_parser import parse_ledger


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match ledger rows to PDF filenames using scoring + veto rules."
    )
    parser.add_argument(
        "--ledger", required=True,
        help="Path to the ledger Excel file",
    )
    parser.add_argument(
        "--files", required=True,
        help="Path to a text file with one filename per line",
    )
    parser.add_argument(
        "--output", default="outputs/results.xlsx",
        help="Path for the output Excel file (default: outputs/results.xlsx)",
    )
    parser.add_argument(
        "--base-path", default="",
        help="Base path/URL for file links (e.g. SharePoint URL or local folder path)",
    )
    args = parser.parse_args()

    # Validate inputs
    ledger_path = Path(args.ledger)
    files_path = Path(args.files)
    if not ledger_path.exists():
        print(f"Error: Ledger file not found: {ledger_path}")
        sys.exit(1)
    if not files_path.exists():
        print(f"Error: Filenames file not found: {files_path}")
        sys.exit(1)

    # Parse inputs
    print(f"Reading ledger: {ledger_path}")
    ledger_rows = parse_ledger(ledger_path)
    print(f"  → {len(ledger_rows)} rows parsed")

    print(f"Reading filenames: {files_path}")
    filenames = [
        line.strip() for line in files_path.read_text().splitlines()
        if line.strip()
    ]
    print(f"  → {len(filenames)} filenames loaded")

    # Run matching
    print("\nRunning matching engine...")
    results, orphans = run_matching(ledger_rows, filenames)

    # Print summary
    strong = sum(1 for r in results if r.status == "Strong")
    good = sum(1 for r in results if r.status == "Good")
    review = sum(1 for r in results if r.status == "Review")
    no_match = sum(1 for r in results if r.status == "No Match")

    print(f"\n{'='*60}")
    print(f"  MATCHING RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total ledger rows:  {len(results)}")
    print(f"  Strong matches:     {strong}")
    print(f"  Good matches:       {good}")
    print(f"  Needs review:       {review}")
    print(f"  No match:           {no_match}")
    print(f"  Orphan files:       {len(orphans)}")
    print(f"{'='*60}")

    # Print detailed results (sorted by score descending)
    sorted_results = sorted(results, key=lambda r: r.score, reverse=True)
    print(f"\n{'Row':<5} {'Vendor':<25} {'Amount':>10} {'Status':<10} {'Score':>6} {'Matched File'}")
    print(f"{'-'*5} {'-'*25} {'-'*10} {'-'*10} {'-'*6} {'-'*40}")
    for r in sorted_results:
        row = r.ledger_row
        file_name = r.matched_file.original_name[:40] if r.matched_file else "—"
        print(
            f"{row.index:<5} {row.vendor:<25} {float(row.amount):>10.2f} "
            f"{r.status:<10} {r.score:>6.1f} {file_name}"
        )

    # Write output
    output_path = Path(args.output)
    write_results(results, orphans, output_path, base_path=args.base_path)
    print(f"\nResults written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()
