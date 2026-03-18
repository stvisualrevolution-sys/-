#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/download/drivecheck-local.zip"
TMP="$(mktemp -d)"
mkdir -p "$TMP/drivecheck"

cp -R "$ROOT/app" "$TMP/drivecheck/"
cp -R "$ROOT/alembic" "$TMP/drivecheck/"
cp "$ROOT/alembic.ini" "$TMP/drivecheck/"
cp "$ROOT/requirements.txt" "$TMP/drivecheck/"
cp "$ROOT/start.command" "$TMP/drivecheck/"
cp -R "$ROOT/web" "$TMP/drivecheck/"
cp -R "$ROOT/samples" "$TMP/drivecheck/"
cp "$ROOT/download/QUICKSTART.md" "$TMP/drivecheck/"

chmod +x "$TMP/drivecheck/start.command"
(cd "$TMP" && zip -r "$OUT" drivecheck >/dev/null)
rm -rf "$TMP"
echo "Built: $OUT"
