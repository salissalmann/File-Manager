"""CLI entry point for the file-to-ledger matching engine."""

from __future__ import annotations

import argparse
import csv
import os
import platform
import subprocess
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from src.engine.matcher import run_matching
from src.output.excel_writer import write_results
from src.output.run_report import write_run_report
from src.output.sharepoint_links import resolve_file_open_url
from src.parsers.ledger_parser import parse_ledger


def _cli_fit(s: str, width: int) -> str:
    """Single-line field with fixed display width so columns stay aligned."""
    t = " ".join(str(s).split())
    if len(t) <= width:
        return t
    if width <= 1:
        return t[:width]
    return t[: width - 1] + "…"


def _load_filenames_and_paths(files_path: Path) -> tuple[list[str], dict[str, str] | None]:
    """Load filenames; for CSV with path column return (names, path_by_filename), else (names, None)."""
    if files_path.suffix.lower() == ".csv":
        names: list[str] = []
        paths: dict[str, str] = {}
        with open(files_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            path_key = None
            if reader.fieldnames:
                for candidate in ("Path From Root", "Path from root", "path_from_root", "PathFromRoot"):
                    if candidate in reader.fieldnames:
                        path_key = candidate
                        break
            for row in reader:
                name = (row.get("Filename") or row.get("filename") or "").strip()
                if not name:
                    continue
                names.append(name)
                if path_key:
                    pr = (row.get(path_key) or "").strip()
                    if pr:
                        paths[name] = pr
        return names, paths if path_key else None
    lines = [
        line.strip()
        for line in files_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return lines, None


def _maybe_open_report(html_path: Path) -> None:
    if os.environ.get("CI"):
        return
    if not sys.stdout.isatty():
        return
    path = html_path.resolve()
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif platform.system() == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
    except OSError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Match ledger rows to PDF filenames using scoring + veto rules."
    )
    parser.add_argument(
        "--ledger",
        required=True,
        help="Path to the ledger Excel file",
    )
    parser.add_argument(
        "--files",
        required=True,
        help="Path to a CSV (Filename + Path From Root) or a text file with one filename per line",
    )
    parser.add_argument(
        "--output",
        default="outputs/results.xlsx",
        help="Path for the output Excel file (default: outputs/results.xlsx)",
    )
    parser.add_argument(
        "--base-path",
        default="",
        help="Base path/URL for file links (e.g. SharePoint URL or Dropbox folder); overrides SharePoint URLs when set",
    )
    parser.add_argument(
        "--no-open-report",
        action="store_true",
        help="Do not open the HTML report in a browser after the run",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    files_path = Path(args.files)
    if not ledger_path.exists():
        print(f"Error: Ledger file not found: {ledger_path}")
        sys.exit(1)
    if not files_path.exists():
        print(f"Error: Filenames file not found: {files_path}")
        sys.exit(1)

    print(f"Reading ledger: {ledger_path}")
    ledger_rows = parse_ledger(ledger_path)
    print(f"  → {len(ledger_rows)} rows parsed")

    print(f"Reading filenames: {files_path}")
    filenames, path_by_filename = _load_filenames_and_paths(files_path)
    print(f"  → {len(filenames)} filenames loaded")
    if path_by_filename is not None:
        print(f"  → path column: {len(path_by_filename)} paths for SharePoint/file links")

    print("\nRunning matching engine...")
    results, orphans = run_matching(ledger_rows, filenames)

    confident = sum(1 for r in results if r.status == "Confident")
    probable = sum(1 for r in results if r.status == "Probable")
    possible = sum(1 for r in results if r.status == "Possible")
    review = sum(1 for r in results if r.status == "Review")
    no_match = sum(1 for r in results if r.status == "No Match")
    ambiguous = sum(1 for r in results if r.is_ambiguous)

    print(f"\n{'='*60}")
    print("  MATCHING RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  Total ledger rows:    {len(results)}")
    print(f"  Confident matches:    {confident}")
    print(f"  Probable matches:     {probable}")
    print(f"  Possible matches:     {possible}")
    print(f"  Needs review:         {review}")
    print(f"  No match:             {no_match}")
    print(f"  Ambiguous:            {ambiguous}")
    print(f"  Orphan files:         {len(orphans)}")
    print(f"{'='*60}")

    _TIER_ORDER = {"Confident": 0, "Probable": 1, "Possible": 2, "Review": 3, "No Match": 4}
    sorted_results = sorted(results, key=lambda r: (_TIER_ORDER.get(r.status, 9), -r.score))
    print(f"\n{'Row':<5} {'Vendor':<25} {'Amount':>10} {'Status':<12} {'Sig':>4} {'Score':>6} {'Matched File':<42} {'Reason':<30}")
    print(f"{'-'*5} {'-'*25} {'-'*10} {'-'*12} {'-'*4} {'-'*6} {'-'*42} {'-'*30}")
    for r in sorted_results:
        row = r.ledger_row
        file_name = r.matched_file.original_name if r.matched_file else "—"
        reason = " + ".join(r.reasons) if r.reasons else "—"
        sig = f"{r.signal_count}/3"
        status = r.status + ("*" if r.is_ambiguous else "")
        print(
            f"{row.index:<5} {_cli_fit(row.vendor, 25):<25} {float(row.amount):>10.2f} "
            f"{_cli_fit(status, 12):<12} {sig:>4} {r.score:>6.1f} "
            f"{_cli_fit(file_name, 42):<42} {_cli_fit(reason, 30):<30}"
        )

    output_path = Path(args.output)
    base_path = (args.base_path or "").strip()
    write_results(
        results,
        orphans,
        output_path,
        base_path=base_path,
        path_by_filename=path_by_filename,
    )
    print(f"\nResults written to: {output_path.resolve()}")

    link_rows: list[tuple[int, str, str]] = []
    for r in results:
        if not r.matched_file:
            continue
        fn = r.matched_file.original_name
        inv_path = (path_by_filename or {}).get(fn, "").strip() if path_by_filename else ""
        if base_path:
            rel = inv_path or fn
            rel = rel.replace("\\", "/")
            base = base_path.rstrip("/").rstrip("\\")
            url = f"{base}/{rel}"
        else:
            url = resolve_file_open_url(inv_path, fn) if path_by_filename is not None else ""
        if url:
            link_rows.append((r.ledger_row.index, fn, url))

    if path_by_filename is not None or base_path:
        print(f"\n{'='*60}")
        print("  FILE LINKS (matched rows)")
        print(f"{'='*60}")
        show = link_rows[:12]
        for idx, fn, url in show:
            print(f"  Row {idx}: {fn}")
            print(f"    {url}")
        if len(link_rows) > len(show):
            print(f"  … and {len(link_rows) - len(show)} more (see HTML report)")
        elif not link_rows:
            print("  (no matched rows with links)")

    report_path = output_path.parent / f"{output_path.stem}_report.html"
    write_run_report(report_path, output_path, link_rows)
    print(f"\nRun report (Excel / Sheets buttons + all links): {report_path.resolve()}")
    if not args.no_open_report:
        _maybe_open_report(report_path)


if __name__ == "__main__":
    main()
