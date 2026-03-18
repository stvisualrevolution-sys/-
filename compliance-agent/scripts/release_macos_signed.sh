#!/bin/bash
set -euo pipefail

# Required env vars:
# APPLE_DEV_ID_APP="Developer ID Application: ..."
# APPLE_DEV_ID_INSTALLER="Developer ID Installer: ..."
# APPLE_ID="you@example.com"
# APPLE_TEAM_ID="XXXXXXXXXX"
# APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx"  (app-specific password)

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build/macos"
APP_DIR="$BUILD/DriveCheck.app"
CONTENTS="$APP_DIR/Contents"
MACOS="$CONTENTS/MacOS"
RES="$CONTENTS/Resources"
OUT="$ROOT/download"
PKG_UNSIGNED="$OUT/DriveCheck-unsigned.pkg"
PKG_SIGNED="$OUT/DriveCheck.pkg"

mkdir -p "$MACOS" "$RES" "$OUT" "$BUILD"

# Copy app payload
cp -R "$ROOT/app" "$RES/"
cp -R "$ROOT/alembic" "$RES/"
cp -R "$ROOT/web" "$RES/"
cp -R "$ROOT/samples" "$RES/"
cp "$ROOT/alembic.ini" "$RES/"
cp "$ROOT/requirements.txt" "$RES/"
cp "$ROOT/start.command" "$RES/"
chmod +x "$RES/start.command"

# Minimal launcher
cat > "$MACOS/DriveCheck" <<'SH'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$DIR"
./start.command
SH
chmod +x "$MACOS/DriveCheck"

# Info.plist
cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>DriveCheck</string>
  <key>CFBundleDisplayName</key><string>DriveCheck</string>
  <key>CFBundleIdentifier</key><string>jp.drivecheck.app</string>
  <key>CFBundleVersion</key><string>1.0.0</string>
  <key>CFBundleShortVersionString</key><string>1.0.0</string>
  <key>CFBundleExecutable</key><string>DriveCheck</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
</dict>
</plist>
PLIST

# Sign app bundle (optional in test)
if [[ -n "${APPLE_DEV_ID_APP:-}" ]]; then
  codesign --deep --force --verify --verbose --timestamp --options runtime --sign "$APPLE_DEV_ID_APP" "$APP_DIR"
fi

# Build installer pkg
pkgbuild --root "$APP_DIR" --install-location "/Applications/DriveCheck.app" "$PKG_UNSIGNED"

if [[ -n "${APPLE_DEV_ID_INSTALLER:-}" ]]; then
  productsign --sign "$APPLE_DEV_ID_INSTALLER" "$PKG_UNSIGNED" "$PKG_SIGNED"
  rm -f "$PKG_UNSIGNED"
  TARGET_PKG="$PKG_SIGNED"
else
  TARGET_PKG="$PKG_UNSIGNED"
fi

# Notarize if credentials provided
if [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_PASSWORD:-}" ]]; then
  xcrun notarytool submit "$TARGET_PKG" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait
  xcrun stapler staple "$TARGET_PKG"
fi

echo "Built macOS package: $TARGET_PKG"
