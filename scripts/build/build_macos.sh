#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."
python3 -m pip install -r requirements/build.txt
python3 -m PyInstaller --clean --noconfirm packaging/macos.spec
echo "Built: dist/nonogram助手.app"
