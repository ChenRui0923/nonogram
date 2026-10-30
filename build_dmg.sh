#!/usr/bin/env bash
set -euo pipefail
APP="dist/Nonogram.app"
DMG="dist/Nonogram-macOS.dmg"
test -d "$APP"
rm -f "$DMG"
STAGE="$(mktemp -d)"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "Nonogram" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
echo "Built: $DMG"
