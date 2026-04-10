#!/usr/bin/env python3
"""Fetch all filenames from a Dropbox shared folder and write to CSV.

Downloads the shared folder as a zip (no auth needed), then lists all files
with their relative paths. Outputs:
  - inputs/dropbox_files.csv  (Filename, Path From Root)

Usage:
  python scripts/fetch_dropbox_files.py
  python scripts/fetch_dropbox_files.py --url "https://www.dropbox.com/scl/fo/..."
"""

import argparse
import csv
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen, Request

DEFAULT_URL = (
    "https://www.dropbox.com/scl/fo/nytt56lkoc7hxh5q7iemb/"
    "AO_7V_NQjyFGkrmq4TXRcBQ?rlkey=fh9n7bwbep9h5firo9wd1ynhc&e=1&st=98ld63iq&dl=0"
)


def _to_download_url(shared_url: str) -> str:
    """Convert a Dropbox shared link to a direct download URL."""
    url = shared_url.replace("dl=0", "dl=1")
    if "dl=1" not in url:
        sep = "&" if "?" in url else "?"
        url += f"{sep}dl=1"
    return url


def _download_zip(url: str, dest: str) -> None:
    """Stream-download a zip from url to dest, printing progress."""
    print(f"Downloading folder as zip...")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    response = urlopen(req)
    total = response.headers.get("Content-Length")
    total = int(total) if total else None

    downloaded = 0
    chunk_size = 1024 * 256  # 256 KB chunks

    with open(dest, "wb") as f:
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 / total
                print(f"\r  {downloaded / 1024 / 1024:.1f} MB / {total / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="", flush=True)
            else:
                print(f"\r  {downloaded / 1024 / 1024:.1f} MB downloaded", end="", flush=True)

    print()  # newline after progress


def _list_files_in_zip(zip_path: str) -> list[tuple[str, str]]:
    """List all files in a zip, returning (filename, relative_path) tuples.

    Strips the top-level folder that Dropbox wraps the zip in.
    """
    files = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            # Skip directories
            if info.is_dir():
                continue

            full_path = PurePosixPath(info.filename)
            filename = full_path.name

            # Skip hidden/system files
            if filename.startswith(".") or filename == "__MACOSX":
                continue
            if any(part.startswith("__MACOSX") for part in full_path.parts):
                continue

            # Strip the top-level zip folder to get relative path
            if len(full_path.parts) > 1:
                relative = str(PurePosixPath(*full_path.parts[1:]))
            else:
                relative = filename

            files.append((filename, relative))

    return files


def main():
    parser = argparse.ArgumentParser(description="Fetch filenames from a Dropbox shared folder.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Dropbox shared folder URL")
    args = parser.parse_args()

    download_url = _to_download_url(args.url)

    # Download to temp file
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        _download_zip(download_url, tmp_path)

        # Verify it's a valid zip
        if not zipfile.is_zipfile(tmp_path):
            print("Error: Downloaded file is not a valid zip. The shared link may be invalid or expired.")
            sys.exit(1)

        files = _list_files_in_zip(tmp_path)
        print(f"Found {len(files)} files.")

        if not files:
            print("Warning: No files found in the folder.")
            sys.exit(0)

        # Write CSV to inputs/
        script_dir = Path(__file__).parent.parent
        output_csv = script_dir / "inputs" / "dropbox_files.csv"
        output_csv.parent.mkdir(parents=True, exist_ok=True)

        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Filename", "Path From Root"])
            for filename, path in sorted(files, key=lambda x: x[1]):
                writer.writerow([filename, path])

        print(f"CSV written: {output_csv.resolve()} ({len(files)} entries)")

    finally:
        Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
