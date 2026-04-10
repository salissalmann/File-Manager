"""Create a cross-platform handoff zip package."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import zipfile


ROOT_DIR = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT_DIR / "dist"
STAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
PKG_DIR = DIST_DIR / f"file-matcher-package-{STAMP}"
ZIP_PATH = DIST_DIR / f"file-matcher-package-{STAMP}.zip"


def _copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def _write_start_here(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "File Matcher Package - Quick Start",
                "=================================",
                "",
                "1) Open terminal in this package folder",
                "2) Install dependencies:",
                "   python -m venv .venv",
                "   .venv\\Scripts\\pip install -r requirements.txt   (Windows)",
                "   .venv/bin/pip install -r requirements.txt         (Mac/Linux)",
                "3) Put your files in inputs/",
                "4) Run matching:",
                "   .venv\\Scripts\\python main.py --ledger \"inputs/Milford-Ledger Clean.xlsx\" --files \"inputs/dropbox_files.csv\" --output \"outputs/results.xlsx\"   (Windows)",
                "   .venv/bin/python main.py --ledger \"inputs/Milford-Ledger Clean.xlsx\" --files \"inputs/dropbox_files.csv\" --output \"outputs/results.xlsx\"         (Mac/Linux)",
                "5) Open result: outputs/results.xlsx",
                "",
                "Detailed guide: docs/run_guide.md",
            ]
        ),
        encoding="utf-8",
    )


def _zip_dir(source_dir: Path, output_zip: Path) -> None:
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in source_dir.rglob("*"):
            zf.write(item, item.relative_to(source_dir.parent))


def main() -> None:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    PKG_DIR.mkdir(parents=True, exist_ok=True)

    # Core project files
    for filename in ("README.md", "Makefile", "requirements.txt", "main.py", "config.py"):
        src = ROOT_DIR / filename
        if src.exists():
            shutil.copy2(src, PKG_DIR / filename)

    for folder in ("src", "docs", "scripts", "tests"):
        src = ROOT_DIR / folder
        if src.exists():
            _copy_tree(src, PKG_DIR / folder)

    # Input/output folders for structure (lightweight)
    (PKG_DIR / "inputs").mkdir(exist_ok=True)
    (PKG_DIR / "outputs").mkdir(exist_ok=True)

    env_template = ROOT_DIR / ".env.template"
    if env_template.exists():
        shutil.copy2(env_template, PKG_DIR / ".env.template")

    _write_start_here(PKG_DIR / "START_HERE.txt")
    _zip_dir(PKG_DIR, ZIP_PATH)

    print("Package created:")
    print(f"  {ZIP_PATH}")


if __name__ == "__main__":
    main()
