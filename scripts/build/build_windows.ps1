$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))
py -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements/build.txt
.\.build-venv\Scripts\pyinstaller.exe --clean --noconfirm packaging/windows.spec
Write-Host "Built: dist\nonogram助手.exe"
