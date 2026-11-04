@echo off
setlocal
cd /d "%~dp0\..\.."
python -m pip install -r requirements/build.txt
python -m PyInstaller --clean --noconfirm packaging/windows.spec
echo.
echo Built: dist\nonogram助手.exe
pause
