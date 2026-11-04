#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install -r requirements-build.txt
python3 -m PyInstaller --clean --noconfirm nonogram_macos.spec
echo "Built: dist/nonogram助手.app"
