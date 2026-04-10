#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
STAMP="$(date +"%Y%m%d-%H%M%S")"
PKG_DIR="$DIST_DIR/file-matcher-package-$STAMP"
ZIP_PATH="$DIST_DIR/file-matcher-package-$STAMP.zip"

mkdir -p "$PKG_DIR"
mkdir -p "$DIST_DIR"

# Core project files
cp "$ROOT_DIR/README.md" "$PKG_DIR/"
cp "$ROOT_DIR/Makefile" "$PKG_DIR/"
cp "$ROOT_DIR/requirements.txt" "$PKG_DIR/"
cp "$ROOT_DIR/main.py" "$PKG_DIR/"
cp "$ROOT_DIR/config.py" "$PKG_DIR/"
cp -R "$ROOT_DIR/src" "$PKG_DIR/src"
cp -R "$ROOT_DIR/docs" "$PKG_DIR/docs"
cp -R "$ROOT_DIR/scripts" "$PKG_DIR/scripts"
cp -R "$ROOT_DIR/tests" "$PKG_DIR/tests"

# Input/output folders for structure (lightweight)
mkdir -p "$PKG_DIR/inputs" "$PKG_DIR/outputs"
if [[ -f "$ROOT_DIR/.env.template" ]]; then
  cp "$ROOT_DIR/.env.template" "$PKG_DIR/"
fi

cat > "$PKG_DIR/START_HERE.txt" <<'EOF'
File Matcher Package - Quick Start
=================================

1) Open terminal in this package folder
2) Run:
   make install
3) Put your files in:
   inputs/
4) Run matching:
   make run
5) Open result:
   outputs/results.xlsx

Detailed guide:
docs/run_guide.md
EOF

(
  cd "$DIST_DIR"
  zip -rq "$(basename "$ZIP_PATH")" "$(basename "$PKG_DIR")"
)

echo "Package created:"
echo "  $ZIP_PATH"
