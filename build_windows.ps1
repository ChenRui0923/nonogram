$ErrorActionPreference = "Stop"
py -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-venv\Scripts\pyinstaller.exe --clean --noconfirm nonogram.spec
Write-Host "Built: dist\nonogram助手.exe"
