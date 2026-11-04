@echo off
setlocal
python -m pip install -r requirements-build.txt
python -m PyInstaller --clean --noconfirm nonogram.spec
echo.
echo Built: dist\nonogram助手.exe
pause
