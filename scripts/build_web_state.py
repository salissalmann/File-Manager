#!/usr/bin/env python3
"""Build outputs/web_state.json for the Next.js dashboard (ledger + files + match results)."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

# Repo root on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.engine.matcher import run_matching
from src.output.json_writer import build_web_state, write_web_state_json
from src.parsers.ledger_parser import parse_ledger


def _load_file_inventory(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    filenames: list[str] = []
    inventory: list[dict[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("Filename") or "").strip()
            path = (row.get("Path From Root") or "").strip()
            if not name:
                continue
            filenames.append(name)
            inventory.append({"filename": name, "pathFromRoot": path})
    return filenames, inventory


def main() -> None:
    parser = argparse.ArgumentParser(description="Export web_state.json for the dashboard.")
    parser.add_argument(
        "--ledger",
        default=str(_ROOT / "inputs" / "Milford-Ledger Clean.xlsx"),
        help="Ledger Excel path",
    )
    parser.add_argument(
        "--files",
        default=str(_ROOT / "inputs" / "dropbox_files.csv"),
        help="Dropbox CSV (Filename, Path From Root)",
    )
    parser.add_argument(
        "--output",
        default=str(_ROOT / "outputs" / "web_state.json"),
        help="Output JSON path",
    )
    parser.add_argument(
        "--file-link-base",
        default="",
        help="Optional URL prefix for file links (e.g. Dropbox folder web URL)",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    files_path = Path(args.files)
    if not ledger_path.exists():
        print(f"Error: ledger not found: {ledger_path}", file=sys.stderr)
        sys.exit(1)
    if not files_path.exists():
        print(f"Error: files CSV not found: {files_path}", file=sys.stderr)
        sys.exit(1)

    base = args.file_link_base or os.environ.get("FILE_LINK_BASE", "")

    print(f"Reading ledger: {ledger_path}")
    ledger_rows = parse_ledger(ledger_path)
    print(f"  → {len(ledger_rows)} rows")

    print(f"Reading file list: {files_path}")
    filenames, inventory = _load_file_inventory(files_path)
    print(f"  → {len(filenames)} files")

    print("Running matcher...")
    results, orphans = run_matching(ledger_rows, filenames)

    state = build_web_state(ledger_rows, inventory, results, orphans, file_link_base=base)
    out = Path(args.output)
    write_web_state_json(state, out)
    print(f"Wrote {out.resolve()}")


if __name__ == "__main__":
    main()
