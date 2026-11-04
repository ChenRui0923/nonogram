# Build from the project root: python -m PyInstaller packaging/windows.spec
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

datas = [(str(ROOT / "nonogram/web/index.html"), "nonogram/web"), (str(ROOT / "assets/fonts"), "assets/fonts")]
hiddenimports = ["cv2", "numpy", "PIL", "pytesseract", "webview"]
hiddenimports += collect_submodules("cv2")

a = Analysis(
    [str(ROOT / "packaging/desktop_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "packaging/runtime_diagnostics.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="nonogram助手",
    icon=str(ROOT / "assets/icons/nonogram.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Double-click friendly: the app opens the browser and does not show a
    # terminal window. Use ``--console`` during development if needed.
    console=False,
)
